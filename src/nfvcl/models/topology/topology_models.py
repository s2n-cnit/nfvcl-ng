from logging import Logger
from nfvcl.models.network import NetworkModel, RouterModel, PduModel
from nfvcl.models.prometheus.prometheus_model import PrometheusServerModel
from nfvcl.models.vim import VimModel
from nfvcl.models.k8s.topology_k8s_model import TopologyK8sModel
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from nfvcl.utils.log import create_logger

logger: Logger = create_logger('Topology model')


class TopoK8SHasBlueprintException(Exception):
    pass


class TopoK8SNotFoundException(Exception):
    pass


class TopologyModel(BaseModel):
    id: Optional[str] = Field(default='topology')
    callback: Optional[HttpUrl] = Field(default=None)
    vims: List[VimModel] = Field(default_factory=list)
    kubernetes: List[TopologyK8sModel] = Field(default_factory=list)
    networks: List[NetworkModel] = Field(default_factory=list)
    routers: List[RouterModel] = Field(default_factory=list)
    pdus: List[PduModel] = Field(default_factory=list)
    # "The list of prometheus server that can be used by the NFVCL (blueprints) to pull data from node exporter" \
    # " installed deployed services. When needed the NFVCL will add a new job to the server in order to pull data."
    prometheus_srv: List[PrometheusServerModel] = Field(default_factory=list)

    def add_prometheus_srv(self, prom_srv: PrometheusServerModel):
        """
        Add a prometheus server instance to the topology
        Args:
            prom_srv: The server to be added
        """
        # The if is working because the __eq__ function has been overwritten in the PrometheusServerModel (on the id).
        if prom_srv in self.prometheus_srv:
            msg_err = "In the topology is already present a Prometheus server with id ->{}<-".format(prom_srv.id)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            self.prometheus_srv.append(prom_srv)

    def del_prometheus_srv(self, prom_srv_id: str, force: bool) -> PrometheusServerModel:
        index = self.find_prom_srv_index(prom_srv_id)
        prom_srv_to_del = self.prometheus_srv[index]

        if len(prom_srv_to_del.targets) > 0 and not force:
            msg_err = ("The prometheus instance to be deleted has configured jobs. You have to remove active "
                       "jobs or force the deletion in the request.")
            logger.error(msg_err)
            raise ValueError(msg_err)

        return self.prometheus_srv.pop(index)

    def upd_prometheus_srv(self, prom_server: PrometheusServerModel) -> PrometheusServerModel:
        """
        Update a prometheus server in the server list. The instance is identified by ID.
        Args:
            prom_server: The server to be updated.

        Returns:
            The updated server
        """
        index = self.find_prom_srv_index(prom_server.id)
        self.prometheus_srv[index] = prom_server
        return prom_server

    def add_k8s_cluster(self, k8s_cluster: TopologyK8sModel):
        """
        Add a k8s cluster instance to the topology
        Args:
            k8s_cluster: The cluster to be added
        """
        if k8s_cluster in self.kubernetes:
            msg_err = 'Kubernetes cluster with name >{}< already exists in the topology'.format(k8s_cluster.name)
            logger.error(msg_err)
            raise ValueError(msg_err)

        self.kubernetes.append(k8s_cluster)

    def del_k8s_cluster(self, k8s_cluster_id: str) -> TopologyK8sModel:
        """
        Delete a k8s cluster instance to the topology. If it was onboarded on OSM it also delete it from there.
        Args:
            k8s_cluster_id: The ID of the cluster to be deleted
        """
        k8s_index = self.find_k8s_cluster_index(k8s_cluster_id)

        # If some blueprint is deployed on the cluster it is not possible to delete it from the topology
        k8s_cluster = self.kubernetes[k8s_index]
        if len(k8s_cluster.deployed_blueprints) > 0:
            raise TopoK8SHasBlueprintException('The cluster has blueprints deployed in it.')

        k8s_deleted = self.kubernetes.pop(k8s_index)

        return k8s_deleted

    def upd_k8s_cluster(self, k8s_cluster: TopologyK8sModel) -> TopologyK8sModel:
        """

        """
        k8s_index = self.find_k8s_cluster_index(k8s_cluster.name)

        # Update in the topology information
        self.kubernetes[k8s_index] = k8s_cluster

        return k8s_cluster

    def add_pdu(self, pdu: PduModel) -> PduModel:
        """
        Add a pdu instance to the topology
        Args:
            pdu: The pdu to be added in the topology
        """
        if pdu in self.pdus:
            msg_err = 'PDU with name >{}< already exists in the topology'.format(pdu.name)
            logger.error(msg_err)
            raise ValueError(msg_err)

        self.pdus.append(pdu)
        return pdu

    def del_pdu(self, pdu_name: str) -> PduModel:
        """
        Delete a PDU from the topology
        Args:
            pdu_name: The name of the PDU used to identify it.

        Returns: The removed PDU
        """
        pdu_index = self.find_pdu_index(pdu_name)
        return self.pdus.pop(pdu_index)

    def upd_pdu(self, pdu: PduModel) -> PduModel:
        """
        Update an existing pdu
        Args:
            pdu: the pdu to be updated (identified by pdu.name) with updated data.

        Returns:
            The updated pdu
        """
        pdu_index = self.find_pdu_index(pdu.name)

        # Update in the topology information
        self.pdus[pdu_index] = pdu

        return pdu

    def get_pdu(self, pdu_name: str) -> PduModel:
        """
        Return the desired PDU from the topology, given the PDU name.
        Args:
            pdu_name: The name of the PDU

        Returns: The PDU

        Raises:
            ValueError if the PDU is not found in the model
        """
        pdu_index = self.find_pdu_index(pdu_name)
        return self.pdus[pdu_index]

    def get_pdus(self) -> List[PduModel]:
        return self.pdus

    # -------------------------------------------------------------------------
    def add_vim(self, vim: VimModel) -> VimModel:
        """
        Add VIM to the topology
        Args:
            vim: the VIM to be added in the topology

        Returns: the added VIM
        Raises: ValueError if already present
        """
        if vim in self.vims:
            msg_err = "The VIM >{}< is already present in the topology.".format(vim.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            self.vims.append(vim)
            return vim

    def del_vim(self, vim_name: str) -> VimModel:
        """
        Remove a VIM from the topology
        Args:
            vim_name: The name of the vim to be removed
        Returns: the removed VIM
        """
        vim_index = self.find_vim_index(vim_name)
        return self.vims.pop(vim_index)

    def upd_vim(self, vim: VimModel) -> VimModel:
        """
        Update a VIM in the topology
        Args:
            vim: The VIM to update (new data with name that identify the instance to update)

        Returns: The updated VIM
        """
        vim_index = self.find_vim_index(vim.name)
        self.vims[vim_index] = vim
        return vim

    def get_vim(self, vim_name) -> VimModel:
        """
        Return the specified VIM from the topology.
        Args:
            vim_name: the name of the VIM to be retrieved
        """
        index_vim = self.find_vim_index(vim_name)
        return self.vims[index_vim]

    def get_vim_by_area(self, area_id: int) -> VimModel:
        """
        Retrieve the first VIM given an area of interest.
        Args:
            area_id: The ID of the area

        Returns: A VIM that have the required area.
        """
        item: VimModel
        vim = next((item for item in self.vims if area_id in item.areas), None)
        if vim is None:
            msg_err = "The VIM of area ->{}<- was not found in the topology.".format(area_id)
            logger.error(msg_err)
            raise ValueError(msg_err)

        return vim

    def get_vim_list_by_area(self, area_id: int) -> List[VimModel]:
        """
        Retrieve VIM list given an area of interest.
        Args:
            area_id: The ID of the area

        Returns: A VIM list that have the required area.
        """
        item: VimModel
        vim_list = [item for item in self.vims if area_id in item.areas]
        if 0 >= len(vim_list):
            msg_err = "The VIM of area ->{}<- was not found in the topology.".format(area_id)
            logger.error(msg_err)
            raise ValueError(msg_err)

        return vim_list

    def get_vim_name_by_area(self, area_id: int) -> str:
        """
        Retrieve the name of the first VIM given an area of interest.
        Args:
            area_id: The ID of the area

        Returns: The name of the VIM that have the required area.
        """
        return self.get_vim_by_area(area_id).name

    def get_vims(self) -> List[VimModel]:
        return self.vims

    # ----------------------------------------------------------------------------

    def add_network(self, network: NetworkModel) -> NetworkModel:
        """
        Add network to the topology.
        Args:
            network: The network to be added in the topology
        Returns:
            The added network
        Raises:
            ValueError if the network is already present.
        """
        if network in self.networks:
            msg_err = "The network >{}< is already present in the topology.".format(network.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            self.networks.append(network)
            return network

    def del_network(self, network_name: str) -> NetworkModel:
        """
        Delete a network from the topology
        Args:
            network_name: The name of the network to be deleted.

        Returns:  The deleted network from the topo
        """
        net_idx = self.find_net_index(network_name)
        return self.networks.pop(net_idx)

    def upd_network(self, network: NetworkModel) -> NetworkModel:
        """
        Update a network in the topology
        Args:
            network: The network to update (new data with name that identify the instance to be updated)

        Returns: The updated network
        """
        net_index = self.find_net_index(network.name)
        self.networks[net_index] = network
        return network

    def get_network(self, network_name) -> NetworkModel:
        """
        Return a network from the topology
        Args:
            network_name: the name of the network to be retrieved

        Returns:
            The desired network from the topology
        """
        net_index = self.find_net_index(network_name)
        return self.networks[net_index]

    def get_networks(self) -> List[NetworkModel]:
        return self.networks

    # --------------------------------------------

    def add_router(self, router: RouterModel) -> RouterModel:
        """
        Add router to the topology
        Args:
            router: The router to be added

        Returns: The just added router
        Raises: ValueError if already present
        """
        if router in self.routers:
            msg_err = "Router >{}< is already present in the topology.".format(router.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        self.routers.append(router)
        return router

    def del_router(self, router_name: str) -> RouterModel:
        """
        Delete a router from the topology
        Args:
            router_name: The name of the router to be deleted.

        Returns: The deleted router from the topo
        """
        router_idx = self.find_router_index(router_name)
        return self.routers.pop(router_idx)

    def upd_router(self, router: RouterModel) -> RouterModel:
        """
        Update a router in the topology
        Args:
            router: The router to be updated

        Returns:
            The updated router
        """
        router_idx = self.find_router_index(router.name)
        self.routers[router_idx] = router
        return router

    def get_router(self, router_name) -> RouterModel:
        """
        Return the desired router, given the name.
        Args:
            router_name: The name of the router

        Returns: The desired router
        """
        router_idx = self.find_router_index(router_name)
        return self.routers[router_idx]

    def get_routers(self) -> List[RouterModel]:
        """
        Return the topology router list.
        """
        return self.routers

    # -------------- FIND ---------------

    def find_prom_srv_index(self, prom_srv_id: str):
        """
        Find the index of prom server in the topology list
        Args:
            prom_srv_id: The identifier of the prometheus server.

        Returns:
            The position of the prom server in the list
        """
        prom_svr_to_search = PrometheusServerModel(id=prom_srv_id)
        try:
            prom_svr_index = self.prometheus_srv.index(prom_svr_to_search)
        except ValueError:
            msg_err = "The prometheus server ->{}<- has not been found".format(prom_srv_id)
            logger.debug(msg_err)
            raise ValueError(msg_err)

        return prom_svr_index

    def find_prom_srv(self, prom_srv_id: str):
        """
        Find the desired prom server in the list and retrieve it.
        Args:
            prom_srv_id: The identifier of the prometheus server.

        Returns: The desired prometheus server instance
        """
        prom_svr_index = self.find_prom_srv_index(prom_srv_id)
        prom_srv = self.prometheus_srv[prom_svr_index]

        return prom_srv

    def find_k8s_cluster(self, cluster_name: str) -> TopologyK8sModel:
        """
        Find the desired k8s cluster instance in the list and retrieve it.
        Args:
            cluster_name: The identifier of the k8s cluster.

        Returns: The desired k8s cluster instance
        """
        index = self.find_k8s_cluster_index(cluster_name)
        return self.kubernetes[index]

    def find_k8s_cluster_by_area(self, area_id: int) -> TopologyK8sModel:
        """
        Find the desired k8s cluster instance in the list and retrieve it, given the area id.
        Args:
            area_id: The identifier of the area for k8s cluster.

        Returns: The desired k8s cluster instance
        """
        index = self.find_k8s_cluster_index_by_area(area_id)
        return self.kubernetes[index]

    def find_k8s_cluster_index(self, cluster_name: str) -> int:
        """
        Find the index of k8s cluster in the topology list
        Args:
            cluster_name: The identifier of the k8s cluster.

        Returns:
            The position of the k8s cluster in the list
        """
        k8s_cluster_index = next((index for index, item in enumerate(self.kubernetes) if item.name == cluster_name), -1)
        if k8s_cluster_index < 0:
            msg_err = "The K8s cluster ->{}<- was not found in the topology.".format(cluster_name)
            logger.debug(msg_err)
            raise TopoK8SNotFoundException(msg_err)

        return k8s_cluster_index

    def find_k8s_cluster_index_by_area(self, area_id: int) -> int:
        """
        Find the index of first k8s cluster in the topology list, given the area id.
        Args:
            area_id: The identifier of the area for the k8s cluster.

        Returns:
            The position of the k8s cluster in the list
        """
        k8s_cluster_index = next((index for index, item in enumerate(self.kubernetes) if area_id in item.areas), -1)
        if k8s_cluster_index < 0:
            msg_err = f"No K8S cluster has been found for area {area_id}"
            logger.debug(msg_err)
            raise TopoK8SNotFoundException(msg_err)

        return k8s_cluster_index

    def find_net_index(self, net_name):
        """
        Find the index of net in the topology list
        Args:
            net_name: The identifier of the net.

        Returns:
            The position of the net in the list
        """
        net_index = next((index for index, item in enumerate(self.networks) if item.name == net_name), -1)
        if net_index < 0:
            msg_err = "The network ->{}<- was not found in the topology.".format(net_name)
            logger.debug(msg_err)
            raise ValueError(msg_err)

        return net_index

    def find_vim_index(self, vim_name):
        """
        Find the index of vim in the topology list
        Args:
            vim_name: The identifier of the k8s cluster.

        Returns:
            The position of the vim in the list
        """
        vim_index = next((index for index, item in enumerate(self.vims) if item.name == vim_name), -1)
        if vim_index < 0:
            msg_err = "The VIM ->{}<- was not found in the topology.".format(vim_name)
            logger.debug(msg_err)
            raise ValueError(msg_err)

        return vim_index

    def find_router_index(self, router_name):
        """
        Find the index of router in the topology list
        Args:
            router_name: The identifier of the k8s cluster.

        Returns:
            The position of the router in the list
        """
        router_index = next((index for index, item in enumerate(self.vims) if item.name == router_name), -1)
        if router_index < 0:
            msg_err = "The router ->{}<- was not found in the topology.".format(router_name)
            logger.debug(msg_err)
            raise ValueError(msg_err)

        return router_index

    def find_pdu_index(self, pdu_name):
        """
        Find the index of pdu in the topology list
        Args:
            pdu_name: The identifier of the pdu.

        Returns:
            The position of the pdu instance in the list

        Raises:
            ValueError if the PDU is not found in the model
        """
        pdu_index = next((index for index, item in enumerate(self.pdus) if item.name == pdu_name), -1)
        if pdu_index < 0:
            msg_err = "The PDU ->{}<- was not found in the topology.".format(pdu_index)
            logger.debug(msg_err)
            raise ValueError(msg_err)

        return pdu_index
