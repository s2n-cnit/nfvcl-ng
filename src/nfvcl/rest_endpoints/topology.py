from fastapi import APIRouter, status, HTTPException
from nfvcl.models.blueprint.blueprint_base_model import BlueprintBaseModel # TODO remove
from nfvcl.models.k8s.blueprint_k8s_model import K8sBlueprintModel
from nfvcl.models.k8s.topology_k8s_model import TopologyK8sModel, K8sModelCreateFromBlueprint
from nfvcl.models.prometheus.prometheus_model import PrometheusServerModel
from nfvcl.models.response_model import OssCompliantResponse, OssStatus
from nfvcl.models.topology import TopologyModel
from nfvcl.models.network import NetworkModel, RouterModel, PduModel
from nfvcl.models.topology.topology_worker_model import TopologyWorkerOperation, TopologyWorkerMessage
from nfvcl.models.vim import VimModel, UpdateVimModel
from nfvcl.rest_endpoints.nfvcl_callback import callback_router
from nfvcl.topology.topology import Topology, topology_lock, build_topology
from nfvcl.topology.topology_worker import topology_msg_queue
from typing import List

from nfvcl.utils.openstack.openstack_utils import check_openstack_instances
from .rest_description import *
from ..utils.database import get_nfvcl_database

topology_router = APIRouter(
    prefix="/v1/topology",
    tags=["Topology"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

@topology_router.get("/", response_model=TopologyModel)
async def get_topology() -> dict:
    """
    Get information regarding the managed topology
    """
    # returning last saved topo
    topology = Topology.from_db(topology_lock)
    return topology.get()


@topology_router.post("/", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes)
async def create_topology(topo: TopologyModel, terraform: bool = False):
    """
    Create the topology for the NFVCL.

    Args:
        topo: The topology to be created

        terraform: Set to true if you want to terraform VIMs upon topology creation

    Returns:

    """
    opt_data = {"terraform": terraform}
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.ADD_TOPOLOGY, topo.model_dump(), opt_data)
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.delete("/", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                        callbacks=callback_router.routes)
async def delete_topology(terraform: bool = False):
    """
    Delete the topology from NFVCL

    Args:
        terraform: set to true if you want to terraform VIMs upon topology creation

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    opt_data = {"terraform": terraform}
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.DEL_TOPOLOGY, {}, opt_data)
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.get("/vim/{vim_id}", response_model=VimModel)
async def get_vim(vim_id: str):
    topology = Topology.from_db(topology_lock)
    try:
        vim: VimModel = topology.get_model().get_vim(vim_id)
        return vim
    except ValueError:
        raise HTTPException(status_code=404, detail="Item not found")


@topology_router.post("/vim", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes)
async def create_vim(vim: VimModel, terraform: bool = False):
    """
    Create a VIM in the topology
    Args:
        vim: The vim to be added to the topology

        terraform: set to true if you want to terraform VIMs upon topology creation

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    opt_data = {"terraform": terraform}
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.ADD_VIM, vim.model_dump(), opt_data)
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.put("/vim/update", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                     callbacks=callback_router.routes)
async def update_vim(updated_vim: UpdateVimModel, terraform: bool = False):
    """
    Update a VIM in the topology
    Args:
        updated_vim: The VIM to be updated

        terraform: set to true if you want to terraform the VIM

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    opt_data = {"terraform": terraform}
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.UPDATE_VIM, updated_vim.model_dump(), opt_data)
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")

@topology_router.get("/vim_check", response_model=OssCompliantResponse, status_code=status.HTTP_200_OK,
                     callbacks=callback_router.routes)
async def check_vims_operation():
    """
    Checks that images (required by nfvcl) and networks (in the vim info) are present in the VIMs belonging to the topology
    """
    topology = build_topology()
    vim_list = topology.get_model().get_vims()

    err_list = check_openstack_instances(vim_list)
    names = [vim.name for vim in err_list]
    if len(err_list)>0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f'The following vims are not working: {names}')
    return OssCompliantResponse(status=OssStatus.ready, detail="All vims are operative.")


@topology_router.delete("/vim/{vim_name}", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                        callbacks=callback_router.routes)
async def delete_vim(vim_name: str, terraform: bool = False):
    """
    Remove a VIM from the topology

    Args:
        vim_name: The name of VIM to be removed

        terraform: set to true if you want to terraform the VIM

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    opt_data = {"terraform": terraform}
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.DEL_VIM, {"vim_name": vim_name}, opt_data)
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.get("/network/{network_id}", response_model=NetworkModel)
async def get_network(network_id: str):
    """
    Return the desired network given the ID

    Args:
        network_id: The ID that identify the network

    Returns:
        NetworkModel containing data on the desired network
    """
    topology = Topology.from_db(topology_lock)
    net: NetworkModel = topology.get_network(network_id)
    return net


@topology_router.post("/network", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes)
async def create_network(network: NetworkModel, terraform: bool = False):
    """
    Add a network to the topology and optionally create it on Openstack

    Args:
        network: The network to be inserted in the topology

        terraform: If the network is created on the VIM. This can raise problems if the network/CIDR already exists.

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    opt_data = {"terraform": terraform}
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.ADD_NET, network.model_dump(), opt_data)
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.delete("/network/{network_id}", response_model=OssCompliantResponse,
                        status_code=status.HTTP_202_ACCEPTED, callbacks=callback_router.routes)
async def delete_network(network_id: str, terraform: bool = False):
    """
    Remove a network from the topology

    Args:
        network_id: The name of network to be removed

        terraform: set to true if you want to terraform the network (delete it on Openstack)

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    opt_data = {"terraform": terraform}
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.DEL_NET, {"network_id": network_id}, opt_data)
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.get("/router/{router_id}", response_model=RouterModel)
async def get_router(router_id: str):
    """
    Return the desired router given the ID

    Args:
        router_id: The ID that identify the router

    Returns:
        RouterModel containing data on the desired network
    """
    topology = Topology.from_db(topology_lock)
    router: RouterModel = topology.get_router(router_id)
    return router


@topology_router.post("/router", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes)
async def create_router(router: RouterModel):
    """
    Add a router to the topology

    Args:
        router: The router to be inserted in the topology

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.ADD_ROUTER, router.model_dump())
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.delete("/router/{router_id}", response_model=OssCompliantResponse,
                        status_code=status.HTTP_202_ACCEPTED,
                        callbacks=callback_router.routes)
async def delete_router(router_id: str):
    """
    Remove a router from the topology

    Args:
        router_id: The name of network to be removed

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.DEL_ROUTER, {"router_id": router_id})
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.get("/pdu/{pdu_id}", response_model=PduModel)
async def get_pdu(pdu_id: str):
    """
    Return the desired PDU given the ID

    Args:
        pdu_id: The ID that identify the PDU

    Returns:
        PduModel containing data on the desired network
    """
    topology = Topology.from_db(topology_lock)
    pdu: PduModel = topology.get_pdu(pdu_id)
    return pdu


@topology_router.get("/pdus", response_model=List[PduModel])
async def get_pdus():
    """
    Return the list of PDUs in the topology

    Returns:
        List[PduModel] containing list of PDU in the topology
    """
    topology = Topology.from_db(topology_lock)
    pdus: List[PduModel] = topology.get_pdus()
    return pdus


@topology_router.post("/pdu", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes)
async def create_pdu(pdu: PduModel):
    """
    Add a PDU to the topology

    Args:
        pdu: The PDU to be inserted in the topology

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.ADD_PDU, pdu.model_dump())
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.delete("/pdu/{pdu_id}", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                        callbacks=callback_router.routes)
async def delete_pdu(pdu_id: str):
    """
    Remove a PDU from the topology

    Args:
        pdu_id: The name of PDU to be removed

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.DEL_PDU, {"pdu_id": pdu_id})
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


# ################################### K8S ###################################
@topology_router.post("/kubernetes", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes, summary=ADD_K8SCLUSTER_SUMMARY,
                      description=ADD_K8SCLUSTER_DESCRIPTION)
async def add_k8s_from_blueprint(cluster_info: K8sModelCreateFromBlueprint):
    """
    Add a K8s cluster, GENERATED WITH A BLUEPRINT, to the topology. Blueprint must exist and NOT be in error state.
    Args:
        cluster_info: The info about the cluster (containing the blueprint ID)

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    # Loading the blueprint from the database and checking that exist. Then converting to model
    blue_item = next((item for item in get_nfvcl_database().find_in_collection('blueprint-instances', {'id': cluster_info.blueprint_ref}, None)))
    if not blue_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail='Blueprint {} not found'.format(cluster_info.blueprint_ref))
    blue_obj = BlueprintBaseModel.model_validate(blue_item) # TODO must update with new Blueprint model from NG
    # Checking the blueprint type
    if blue_obj.type not in ['K8sBeta']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Blueprint {} is not a Kubernetes cluster'
                            .format(cluster_info.blueprint_ref))
    # Checking that the blueprint is not in error state
    if blue_obj.status == 'error':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Blueprint {} is in error state'.format(cluster_info.blueprint_ref))
    # Building the k8s blue model
    k8s_blue_model = K8sBlueprintModel.model_validate(blue_obj.conf)
    # Converting the blueprint K8s representation to the topology one and then adding it to topology
    k8s_topo_model = k8s_blue_model.parse_to_k8s_topo_model()
    # Using data from the request to adjust data from the blueprint
    k8s_topo_model.nfvo_onboard = cluster_info.nfvo_onboard
    k8s_topo_model.name = cluster_info.name

    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.ADD_K8S, k8s_topo_model.model_dump())
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.post("/kubernetes_external", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes, summary=ADD_EXTERNAL_K8SCLUSTER_SUMMARY,
                      description=ADD_EXTERNAL_K8SCLUSTER)
async def add_external_k8scluster(cluster: TopologyK8sModel):
    """
    Add a K8s cluster, EXTERNAL, to the topology
    Args:
        cluster: The info about the k8s cluster.

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    cluster.provided_by = 'external'
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.ADD_K8S, cluster.model_dump())
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.put("/kubernetes/update", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                     callbacks=callback_router.routes, summary=UPD_K8SCLUSTER_SUMMARY,
                     description=UPD_PROM_SRV_DESCRIPTION)
async def update_k8scluster(cluster: TopologyK8sModel):
    """
    Update a K8s cluster in the topology
    Args:
        cluster: The UPDATED info about the k8s cluster.

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    topology = Topology.from_db(topology_lock)
    try:
        topology.get_k8s_cluster(cluster.name)
    except ValueError:
        return OssCompliantResponse(status=OssStatus.failed, detail="K8s cluster to update has not been found.")

    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.UPDATE_K8S, cluster.model_dump())
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.delete("/kubernetes/{cluster_name}", response_model=OssCompliantResponse,
                        status_code=status.HTTP_202_ACCEPTED, callbacks=callback_router.routes)
async def delete_k8scluster(cluster_name: str):
    """
    Remove a K8s cluster from the topology
    Args:
        cluster_name: The name of the K8s cluster to be removed from the topology.

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.DEL_K8S, {"cluster_name": cluster_name})
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.get("/kubernetes", response_model=List[TopologyK8sModel])
async def get_k8scluster():
    """
    Return a list of all k8s clusters in the topology.

    Returns:
        The list of k8s clusters.
    """

    topology = Topology.from_db(topology_lock)
    return topology.get_k8s_clusters()


@topology_router.post("/prometheus", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes, summary=ADD_PROM_SRV_SUMMARY,
                      description=ADD_K8SCLUSTER_DESCRIPTION)
async def add_prom(prom_srv: PrometheusServerModel):
    """
    Add a prometheus server, EXTERNAL, to the topology
    Args:
        prom_srv: The info about the prometheus server.

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.ADD_PROM, prom_srv.model_dump())
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.put("/prometheus", response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                     callbacks=callback_router.routes, summary=UPD_PROM_SRV_SUMMARY,
                     description=UPD_PROM_SRV_DESCRIPTION)
async def upd_prom(prom_srv: PrometheusServerModel):
    """
    Update a prometheus server in the topology
    Args:
        prom_srv: The UPDATED info about the prometheus server.

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    topology = Topology.from_db(topology_lock)
    try:
        topology.get_prometheus_server(prom_srv.id)
    except ValueError:
        return OssCompliantResponse(status=OssStatus.failed, detail="K8s cluster to update has not been found.")

    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.UPD_PROM, prom_srv.model_dump())
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.delete("/prometheus/{prom_srv_id}", response_model=OssCompliantResponse,
                        status_code=status.HTTP_202_ACCEPTED, callbacks=callback_router.routes,
                        summary=DEL_PROM_SRV_SUMMARY, description=DEL_PROM_SRV_DESCRIPTION)
async def del_prom(prom_srv_id: str):
    """
    Remove a prometheus server from the topology
    Args:
        prom_srv_id: The name of the prometheus server to be removed from the topology.

    Returns:
        OssCompliantResponse that confirm the operation has been submitted
    """
    worker_msg = TopologyWorkerMessage.build_worker_message(TopologyWorkerOperation.DEL_PROM, {"prom_srv_id": prom_srv_id})
    topology_msg_queue.put(worker_msg.model_dump())
    return OssCompliantResponse(detail="Operation submitted")


@topology_router.get("/prometheus", response_model=List[PrometheusServerModel], status_code=status.HTTP_202_ACCEPTED,
                     callbacks=callback_router.routes, summary=GET_PROM_LIST_SRV_SUMMARY,
                     description=GET_PROM_LIST_SRV_DESCRIPTION,
                     name="TOPO Get Prometheus servers")
async def get_prom_list():
    """
    Return a list of prometheus server in the topology

    Returns:
        The list of prometheus server.
    """
    topology = Topology.from_db(topology_lock)
    prom_list = topology.get_prometheus_servers_model()
    return prom_list


@topology_router.get("/prometheus/{prometheus_id}", response_model=PrometheusServerModel, status_code=status.HTTP_202_ACCEPTED,
                     callbacks=callback_router.routes, summary=GET_PROM_SRV_SUMMARY,
                     description=GET_PROM_SRV_DESCRIPTION)
async def get_prom(prometheus_id: str):
    topology = Topology.from_db(topology_lock)
    try:
        prom_inst = topology.get_prometheus_server(prom_server_id=prometheus_id)
    except ValueError:
        return OssCompliantResponse(status=OssStatus.failed, detail="Prometheus server has not been found.")

    return prom_inst
