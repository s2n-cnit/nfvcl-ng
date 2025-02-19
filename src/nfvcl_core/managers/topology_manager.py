from typing import Optional, List, Union, Callable

from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address

from nfvcl_core_models.pre_work import PreWorkCallbackResponse, run_pre_work_callback
from nfvcl_core_models.response_model import OssCompliantResponse, OssStatus

from nfvcl_core_models.topology_k8s_model import TopologyK8sModel
from nfvcl_core.database import TopologyRepository
from nfvcl_core.managers import GenericManager
from nfvcl_core_models.network import NetworkModel, RouterModel, PduModel
from nfvcl_core_models.network.network_models import IPv4ReservedRange, PoolAssignation, IPv4Pool, MultusInterface
from nfvcl_core_models.prometheus.prometheus_model import PrometheusServerModel
from nfvcl_core_models.topology_models import TopologyModel
from nfvcl_core_models.vim import VimModel


class TopologyManager(GenericManager):
    def __init__(self, topology_repository: TopologyRepository):
        super().__init__()
        self._topology_repository = topology_repository
        self._topology: Optional[TopologyModel] = self._topology_repository.get_topology()

    def save_to_db(self):
        self._topology_repository.save_topology(self._topology)

    def get_topology(self) -> TopologyModel:
        if self._topology:
            return self._topology
        raise NFVCLCoreException("No topology found")

    def create_topology(self, topology: TopologyModel) -> TopologyModel:
        self.logger.debug(topology)
        self._topology = topology
        self._topology_repository.save_topology(topology)
        return topology

    def delete_topology(self) -> None:
        self._topology_repository.delete_all()
        self._topology = None

    def get_vim(self, vim_id: str) -> VimModel:
        return self._topology.get_vim(vim_id)

    def get_vim_name_from_area_id(self, area_id: int) -> str:
        return self._topology.get_vim_name_by_area(area_id)

    def get_vim_from_area_id_model(self, area: int) -> VimModel:
        return self._topology.get_vim_by_area(area)

    def create_vim(self, vim: VimModel) -> VimModel:
        for vim_already_present in self._topology.vims:
            # Check if vim with the same name already exists
            if vim_already_present.name == vim.name:
                raise NFVCLCoreException(f"VIM with name {vim.name} already exists")

            # Check overlapping areas
            if len(set(vim_already_present.areas) & set(vim.areas)) > 0:
                raise NFVCLCoreException(f"Some of the areas are already assigned to a VIM")

        self._topology.add_vim(vim)
        self.save_to_db()
        return vim

    def delete_vim(self, vim_id: str) -> None:
        self._topology.del_vim(vim_id)
        self.save_to_db()

    def update_vim(self, vim: VimModel) -> VimModel:
        self._topology.upd_vim(vim)
        self.save_to_db()
        return vim

    ############################ Network ########################################

    def get_network(self, network_id: str) -> NetworkModel:
        return self._topology.get_network(network_id)

    def create_network(self, network: NetworkModel) -> NetworkModel:
        self._topology.add_network(network)
        self.save_to_db()
        return network

    def update_network(self, network: NetworkModel) -> NetworkModel:
        self._topology.upd_network(network)
        self.save_to_db()
        return network

    def add_allocation_pool_to_network(self, network_id: str, allocation_pool: IPv4Pool) -> IPv4Pool:
        network = self._topology.get_network(network_id)
        added_pool = network.add_allocation_pool(allocation_pool)
        self.save_to_db()
        return added_pool

    def remove_allocation_pool_from_network(self, network_id: str, allocation_pool_name: str) -> IPv4Pool:
        network = self._topology.get_network(network_id)
        removed_pool = network.remove_allocation_pool(allocation_pool_name)
        self.save_to_db()
        return removed_pool

    def reserve_range_to_k8s_cluster(self, network_id: str, k8s_cluster_id: str, length: int) -> List[IPv4ReservedRange]:
        # Getting info
        network = self._topology.get_network(network_id)
        k8s_cluster = self._topology.get_k8s_cluster(k8s_cluster_id)
        k8s_network = k8s_cluster.get_network(network_id)
        # Looking for available ranges and reserve them
        reserved_networks = network.reserve_range(owner=k8s_cluster.name, assigned_to="K8S Topology cluster", length=length)
        # Adding to the K8s cluster the id of the reserved range
        k8s_network.ip_pools.extend([res_range.name for res_range in reserved_networks])

        self.save_to_db()
        return reserved_networks

    def release_range_from_k8s_cluster(self, network_id: str, reserved_range_name: str, k8s_cluster_id: str) -> IPv4ReservedRange:
        # Getting info
        network = self._topology.get_network(network_id)
        removed_range: Union[IPv4ReservedRange, None] = None
        for reserved_range in network.reserved_ranges:
            if reserved_range.assigned_to == PoolAssignation.K8S_CLUSTER.value and reserved_range.name == reserved_range_name:
                removed_range = network.release_range(reserved_range_name=reserved_range_name)
                break
        if removed_range is None:
            raise NFVCLCoreException(f"Reserved range {reserved_range_name} not found in network {network_id}")
        # Removing from the K8s cluster the id of the reserved range
        k8s_cluster = self._topology.get_k8s_cluster(k8s_cluster_id)
        k8s_cluster.release_ip_pool(removed_range.name)

        self.save_to_db()
        return removed_range

    def get_reserved_ranges_from_network(self, network_id: str) -> List[IPv4ReservedRange]:
        network = self._topology.get_network(network_id)
        return network.reserved_ranges

    def get_reserved_range_from_network(self, network_id: str, reserved_range_name: str) -> IPv4ReservedRange:
        return self._topology.get_network(network_id).get_reserved_range(reserved_range_name)

    def delete_network(self, network_id: str) -> None:
        self._topology.delete_network(network_id)
        self.save_to_db()

    ############################ Router ########################################

    def get_router(self, router_id: str) -> RouterModel:
        return self._topology.get_router(router_id)

    def create_router(self, router: RouterModel) -> RouterModel:
        self._topology.add_router(router)
        self.save_to_db()
        return router

    def delete_router(self, router_id: str) -> None:
        self._topology.delete_router(router_id)
        self.save_to_db()

    ############################ PDUs ########################################

    def get_pdu(self, pdu_id: str) -> PduModel:
        """
        Return the desired PDU given the ID

        Args:
            pdu_id: The ID that identify the PDU

        Returns:
            PduModel containing data on the desired network
        """
        return self._topology.get_pdu(pdu_id)

    def create_pdu(self, pdu: PduModel) -> PduModel:
        """
        Add a PDU to the topology

        Args:
            pdu: The PDU to be inserted in the topology
        """
        self._topology.add_pdu(pdu)
        self.save_to_db()
        return pdu

    def delete_pdu(self, pdu_id: str) -> None:
        """
        Remove a PDU from the topology

        Args:
            pdu_id: The name of PDU to be removed
        """
        if self._topology.get_pdu(pdu_id).locked_by:
            raise NFVCLCoreException(f"PDU {pdu_id} is locked by {self._topology.get_pdu(pdu_id).locked_by}")

        self._topology.del_pdu(pdu_id)
        self.save_to_db()

    def get_pdus(self) -> List[PduModel]:
        """
        Return the list of PDUs in the topology

        Returns:
            List[PduModel] containing list of PDU in the topology
        """
        return self._topology.get_pdus()

    ############################ Kubernetes ########################################

    def get_kubernetes_list(self) -> List[TopologyK8sModel]:
        return self._topology.kubernetes

    def get_k8s_cluster_by_id(self, cluster_id: str) -> TopologyK8sModel:
        return self._topology.get_k8s_cluster(cluster_id)

    def add_kubernetes(self, k8s: TopologyK8sModel) -> TopologyK8sModel:
        self._topology.add_k8s_cluster(k8s)
        self.save_to_db()
        return k8s

    def update_kubernetes(self, cluster: TopologyK8sModel, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> TopologyK8sModel:
        try:
            self.get_k8s_cluster_by_id(cluster.name)
        except ValueError:
            run_pre_work_callback(pre_work_callback, async_return=OssCompliantResponse(status=OssStatus.failed, detail="K8s cluster to update has not been found."))

        self._topology.upd_k8s_cluster(cluster)
        self.save_to_db()
        return cluster

    def delete_kubernetes(self, k8s_id: str) -> None:
        self._topology.del_k8s_cluster(k8s_id)
        self.save_to_db()

    def get_k8s_cluster_by_area(self, area_id: int) -> TopologyK8sModel:
        """
        Get the k8s cluster from the topology. This method could be duplicated but in this case handle HTTP exceptions
        that give API user an idea of what is going wrong.

        Args:

            area_id: the area id in of the cluster to get.

        Returns:

            The matching k8s cluster or Throw HTTPException if NOT found.
        """
        k8s_clusters: List[TopologyK8sModel] = self._topology.get_k8s_clusters()
        match = next((x for x in k8s_clusters if area_id in x.areas), None)

        if match:
            return match
        else:
            error_msg = f"K8s cluster not found in area {area_id}"
            self.logger.error(error_msg)
            raise NFVCLCoreException(error_msg)

    def reserve_k8s_multus_ip(self, k8s_id: str, network_name: str) -> MultusInterface:
        # Getting Info (raise error if not found)
        cluster = self.get_k8s_cluster_by_id(k8s_id)
        cluster_network = cluster.get_network(network_name)
        if cluster_network.ip_pools is None or len(cluster_network.ip_pools) == 0:
            raise NFVCLCoreException(f"No IP pools assigned to the network {network_name} for the K8s cluster {k8s_id}")
        if cluster_network.interface_name is None:
            raise NFVCLCoreException(f"No interface name assigned to the network {network_name} in the K8s cluster {k8s_id}")
        network = self.get_network(network_name)

        assigned_ip: SerializableIPv4Address | None = None
        for ip_pool in cluster_network.ip_pools:
            topology_network_reserved_pool = self.get_network(network_name).get_reserved_range(ip_pool)
            assigned_ip = topology_network_reserved_pool.assign_ip_address()
            if assigned_ip is not None:
                break
        if assigned_ip is None:
            raise NFVCLCoreException(f"No available IP in the network {network_name} for the K8s cluster {k8s_id}. Reserved ranges are empty or all IPs have been reserved")

        multus_info = MultusInterface(
            host_interface=cluster_network.interface_name,
            ip_address=assigned_ip,
            network_name=network.name,
            gateway_ip=network.gateway_ip,
            network_cidr=network.cidr,
            prefixlen=network.cidr.prefixlen
        )

        self.save_to_db()

        return multus_info

    def release_k8s_multus_ip(self, k8s_id: str, network_name: str, ip_address: SerializableIPv4Address) -> MultusInterface:
        """
        Release the IP address reserved for a k8s cluster using Multus from the network
        Args:
            k8s_id: The cluster to which the IP as been assigned
            ip_address: The IP address to be released
            network_name: The network in which the IP has been reserved

        Returns:
            The released IP address
        """
        network = self.get_network(network_name)
        reserved_range = network.get_reserved_range_by_ip(ip_address)
        if reserved_range.assigned_to == PoolAssignation.K8S_CLUSTER.value and reserved_range.owner == k8s_id:
            reserved_range.release_ip_address(ip_address)
        self.save_to_db()
        return ip_address

    ############################ Prometheus ########################################

    def get_prometheus_list(self) -> List[PrometheusServerModel]:
        return self._topology.prometheus_srv

    def get_prometheus(self, prometheus_id: str) -> PrometheusServerModel:
        return self._topology.find_prom_srv(prometheus_id)

    def add_prometheus(self, prometheus: PrometheusServerModel):
        self._topology.add_prometheus_srv(prometheus)
        self.save_to_db()

    def update_prometheus(self, prometheus: PrometheusServerModel):
        self._topology.upd_prometheus_srv(prometheus)
        self.save_to_db()

    def delete_prometheus(self, prometheus_id: str):
        self._topology.del_prometheus_srv(prometheus_id, False)
        self.save_to_db()

    def update_pdu(self, pdu: PduModel):
        """
        Update an existing pdu
        Args:
            pdu: the pdu to be updated (identified by pdu.name) with updated data.
        """
        self._topology.upd_pdu(pdu)
        self.save_to_db()
