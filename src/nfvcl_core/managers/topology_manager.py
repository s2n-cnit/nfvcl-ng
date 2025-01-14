from typing import Optional, List, Union, Callable

from nfvcl_core.models.pre_work import PreWorkCallbackResponse, run_pre_work_callback
from nfvcl_core.models.response_model import OssCompliantResponse, OssStatus

from nfvcl.models.k8s.topology_k8s_model import TopologyK8sModel
from nfvcl_core.database import TopologyRepository
from nfvcl_core.managers import GenericManager
from nfvcl_core.models.network import NetworkModel, RouterModel, PduModel
from nfvcl_core.models.network.network_models import IPv4ReservedRange
from nfvcl_core.models.prometheus.prometheus_model import PrometheusServerModel
from nfvcl_core.models.topology_models import TopologyModel
from nfvcl_core.models.vim import VimModel


class TopologyManager(GenericManager):
    def __init__(self, topology_repository: TopologyRepository):
        super().__init__()
        self._topology_repository = topology_repository
        self._topology: Optional[TopologyModel] = self._topology_repository.get_topology()

    def get_topology(self) -> TopologyModel:
        if self._topology:
            return self._topology
        raise Exception("No topology found")

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
                raise Exception(f"VIM with name {vim.name} already exists")

            # Check overlapping areas
            if len(set(vim_already_present.areas) & set(vim.areas)) > 0:
                raise Exception(f"Some of the areas are already assigned to a VIM")

        self._topology.add_vim(vim)
        self._topology_repository.save_topology(self._topology)
        return vim

    def delete_vim(self, vim_id: str) -> None:
        self._topology.del_vim(vim_id)
        self._topology_repository.save_topology(self._topology)

    def update_vim(self, vim: VimModel) -> VimModel:
        self._topology.upd_vim(vim)
        self._topology_repository.save_topology(self._topology)
        return vim

    def get_network(self, network_id: str) -> NetworkModel:
        return self._topology.get_network(network_id)

    def create_network(self, network: NetworkModel) -> NetworkModel:
        self._topology.add_network(network)
        self._topology_repository.save_topology(self._topology)
        return network

    def delete_network(self, network_id: str) -> None:
        self._topology.delete_network(network_id)
        self._topology_repository.save_topology(self._topology)

    def get_router(self, router_id: str) -> RouterModel:
        return self._topology.get_router(router_id)

    def create_router(self, router: RouterModel) -> RouterModel:
        self._topology.add_router(router)
        self._topology_repository.save_topology(self._topology)
        return router

    def delete_router(self, router_id: str) -> None:
        self._topology.delete_router(router_id)
        self._topology_repository.save_topology(self._topology)

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
        self._topology_repository.save_topology(self._topology)
        return pdu

    def delete_pdu(self, pdu_id: str) -> None:
        """
        Remove a PDU from the topology

        Args:
            pdu_id: The name of PDU to be removed
        """
        self._topology.del_pdu(pdu_id)
        self._topology_repository.save_topology(self._topology)

    def get_pdus(self) -> List[PduModel]:
        """
        Return the list of PDUs in the topology

        Returns:
            List[PduModel] containing list of PDU in the topology
        """
        return self._topology.get_pdus()

    def get_kubernetes_list(self) -> List[TopologyK8sModel]:
        return self._topology.kubernetes

    def get_k8s_cluster_by_id(self, cluster_id: str) -> TopologyK8sModel:
        return self._topology.get_k8s_cluster(cluster_id)

    def add_kubernetes(self, k8s: TopologyK8sModel) -> TopologyK8sModel:
        self._topology.add_k8s_cluster(k8s)
        self._topology_repository.save_topology(self._topology)
        return k8s

    def update_kubernetes(self, cluster: TopologyK8sModel, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> TopologyK8sModel:
        try:
            self.get_k8s_cluster_by_id(cluster.name)
        except ValueError:
            run_pre_work_callback(pre_work_callback, PreWorkCallbackResponse(async_return=OssCompliantResponse(status=OssStatus.failed, detail="K8s cluster to update has not been found.")))

        self._topology.upd_k8s_cluster(cluster)
        self._topology_repository.save_topology(self._topology)
        return cluster

    def delete_kubernetes(self, k8s_id: str) -> None:
        self._topology.del_k8s_cluster(k8s_id)
        self._topology_repository.save_topology(self._topology)

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
            # TODO change exception type
            raise Exception(error_msg)

    def release_ranges(self, owner: str, ip_range: IPv4ReservedRange = None, net_name: str = None) -> IPv4ReservedRange:
        """
        Release a reserved range. It is possible by giving the owner name or the full specification.
        Args:
            owner: The owner of the reservation. Mandatory
            ip_range: Optional IP range, in case there are multiple reservation.
            net_name: Optional network name in witch the reservation is searched.
        Returns:
            The deleted IP range reservation
        """
        removed_range: Union[IPv4ReservedRange, None] = None

        if net_name is None:
            # Iterating over all the networks because no network was given.
            for network in self._topology.networks:
                removed_range = network.release_range(owner=owner, ip_range=ip_range)
                if removed_range:
                    break
        else:
            # Looking for the reservation to be removed in the desired network
            network = self._topology.get_network(net_name)
            removed_range = network.release_range(owner=owner, ip_range=ip_range)

        if removed_range is None:
            msg_err = f"The range owned by {owner} has NOT been found and removed."
            self.logger.error(msg_err)
        else:
            self._topology_repository.save_topology(self._topology)
            return removed_range


    def get_prometheus_list(self) -> List[PrometheusServerModel]:
        return self._topology.prometheus_srv

    def get_prometheus(self, prometheus_id: str) -> PrometheusServerModel:
        return self._topology.find_prom_srv(prometheus_id)

    def add_prometheus(self, prometheus: PrometheusServerModel):
        self._topology.add_prometheus_srv(prometheus)
        self._topology_repository.save_topology(self._topology)

    def update_prometheus(self, prometheus: PrometheusServerModel):
        self._topology.upd_prometheus_srv(prometheus)
        self._topology_repository.save_topology(self._topology)

    def delete_prometheus(self, prometheus_id: str):
        self._topology.del_prometheus_srv(prometheus_id, False)
        self._topology_repository.save_topology(self._topology)
