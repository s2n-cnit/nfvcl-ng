import logging

from fastapi import APIRouter, Query, status, HTTPException
from models.k8s import K8sModel, K8sModelCreateFromBlueprint, K8sModelCreateFromExternalCluster, K8sModelUpdateRequest
from models.topology import TopologyModel
from models.network import NetworkModel, RouterModel, PduModel
from models.vim import VimModel, UpdateVimModel
from rest_endpoints.rest_callback import RestAnswer202, CallbackRequest
from rest_endpoints.nfvcl_callback import callback_router
from topology.topology import Topology, topology_msg_queue, topology_lock
from main import db, nbiUtil
from pydantic import AnyHttpUrl
from typing import Union, List
from utils import get_daemon_sets, parse_k8s_clusters_from_dict, get_k8s_config_from_file_content, check_installed_daemons
from .rest_description import *

topology_router = APIRouter(
    prefix="/v1/topology",
    tags=["Topology"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


def produce_msg_worker(resource_type: str, resource_id: str, resource_ops: str, msg_body: Union[dict, None] = None):
    topology = Topology.from_db(db, nbiUtil, topology_lock)
    if resource_type in topology.get():
        try:
            obj = next(item for item in topology.get()[resource_type] if item['name'] == resource_id)
        except StopIteration:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="[{}] {} not found".format(resource_type, resource_id))
        if not msg_body:
            msg_body = obj
        msg_body.update({'ops_type': resource_ops})

        topology_msg_queue.put(msg_body)
        return {'id': 'topology'}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topology not initialized")


def get_topology_item(resource_type, resource_id):
    topology = Topology.from_db(db, nbiUtil, topology_lock)
    if resource_type in topology.get():
        try:
            obj = next(item for item in topology.get()[resource_type] if item['name'] == resource_id)
            return obj
        except StopIteration:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="[{}] {} not found".format(resource_type, resource_id))

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topology not initialized")


class TopologyModelPost(TopologyModel):
    callback: AnyHttpUrl = None


@topology_router.get("/", response_model=TopologyModel)
async def get_topology() -> dict:
    """
    Get information regarding the managed topology
    """
    # returning last saved topo
    topology = Topology.from_db(db, nbiUtil, topology_lock)
    return topology.get()


@topology_router.post("/", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes)
async def create_topology(
        topo: TopologyModel,
        terraform: bool = Query(default=False,
                                description="set to true if you want to terraform VIMs upon topology creation"),
):
    msg = topo.dict()
    msg.update({'ops_type': 'add_topology', 'terraform': terraform})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.delete("/", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                        callbacks=callback_router.routes)
async def delete_topology(
        msg_body: CallbackRequest,
        terraform: bool = Query(default=False,
                                description="set to true if you want to terraform VIMs upon topology creation")
):
    topology = Topology.from_db(db, nbiUtil, topology_lock)
    if not topology:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="topology not declared")
    msg = msg_body.dict()
    msg.update({'ops_type': 'del_topology', 'terraform': terraform})
    print(msg)
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.get("/vim/{vim_id}", response_model=VimModel)
async def get_vim(vim_id: str):
    return get_topology_item('vims', vim_id)


@topology_router.post("/vim", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes)
async def create_vim(
        vim: VimModel,
        terraform: bool = Query(default=False,
                                description="set to true if you want to terraform VIMs upon topology creation")
):
    msg = vim.dict()
    msg.update({'ops_type': 'add_vim', 'terraform': terraform})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.put("/vim/{vim_id}", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                     callbacks=callback_router.routes)
async def update_vim(
        vim_id: str,
        updated_vim: UpdateVimModel,
        terraform: bool = Query(default=False,
                                description="set to true if you want to terraform the VIM")
):
    msg = updated_vim.dict()
    msg.update({'terraform': terraform})
    return produce_msg_worker('vims', vim_id, 'update_vim', msg_body=msg)


@topology_router.delete(
    "/vim/{vim_id}",
    response_model=RestAnswer202,
    status_code=status.HTTP_202_ACCEPTED,
    callbacks=callback_router.routes
)
async def delete_vim(
        vim_id: str,
        terraform: bool = Query(default=False,
                                description="set to true if you want to terraform the VIM")
):
    msg = get_topology_item('vims', vim_id)
    msg.update({'terraform': terraform})
    return produce_msg_worker('vims', vim_id, 'del_vim', msg_body=msg)


@topology_router.get("/network/{network_id}", response_model=NetworkModel)
async def get_network(network_id: str):
    return get_topology_item('networks', network_id)


@topology_router.post("/network", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes)
async def create_network(network: NetworkModel):
    msg = network.dict()
    msg.update({'ops_type': 'add_net'})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.delete(
    "/network/{network_id}",
    response_model=RestAnswer202,
    status_code=status.HTTP_202_ACCEPTED,
    callbacks=callback_router.routes
)
async def delete_network(network_id: str):
    return produce_msg_worker('networks', network_id, 'del_net')


@topology_router.get("/router/{router_id}", response_model=RouterModel)
async def get_router(router_id: str):
    return get_topology_item('routers', router_id)


@topology_router.post("/router", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes)
async def create_router(router: RouterModel):
    msg = router.dict()
    msg.update({'ops_type': 'add_router'})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.delete(
    "/router/{router_id}",
    response_model=RestAnswer202,
    status_code=status.HTTP_202_ACCEPTED,
    callbacks=callback_router.routes
)
async def delete_router(router_id: str):
    return produce_msg_worker('routers', router_id, 'del_router')


@topology_router.get("/pdu/{pdu_id}", response_model=PduModel)
async def get_pdu(pdu_id: str):
    return get_topology_item('pdus', pdu_id)


@topology_router.get("/pdus", response_model=List[PduModel])
async def get_pdus():
    topology = Topology.from_db(db, nbiUtil, topology_lock)
    return topology.get_pdus()


@topology_router.post("/pdu", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes)
async def create_pdu(router: PduModel):
    msg = router.dict()
    msg.update({'ops_type': 'add_pdu'})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.delete(
    "/router/{router_id}",
    response_model=RestAnswer202,
    status_code=status.HTTP_202_ACCEPTED,
    callbacks=callback_router.routes
)
async def delete_router(router_id: str):
    return produce_msg_worker('pdus', router_id, 'del_pdu')


# ################################### K8s ###################################

@topology_router.post("/kubernetes", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes, summary=ADD_K8SCLUSTER_SUMMARY,
                      description=ADD_K8SCLUSTER_DESCRIPTION)
async def create_k8scluster(cluster: K8sModelCreateFromBlueprint):
    msg = cluster.dict()
    msg.update({'ops_type': 'add_k8s'})
    if 'blueprint_ref' not in msg or not msg['blueprint_ref']:
        # See in following methods
        err_msg = "Blueprint reference (blueprint_ref) is mandatory. If you want to add an external k8s use POST on " \
                  "{base_url}/v1/topology/kubernetes_external instead of /v1/topology/kubernetes"
        logging.error(err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    else:
        msg.update({'provided_by': 'blueprint'})
        blue_item = next((item for item in db.find_DB('blueprint-instances', {'id': msg['blueprint_ref']})), None)
        if not blue_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail='Blueprint {} not found'.format(msg['blueprint_ref']))
        if blue_item['type'] != 'K8s':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail='Blueprint {} is not a Kubernetes cluster'
                                .format(msg['blueprint_ref']))
        if blue_item['type'] == 'error':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail='Blueprint {} is in error state'.format(msg['blueprint_ref']))

        core_area = next(item['id'] for item in blue_item['conf']['areas'] if item['core'])
        topology = Topology.from_db(db, nbiUtil, topology_lock)
        vim_name = topology.get_vim_from_area_id(core_area)['name']

        msg.update({
            'credentials': blue_item['conf']['config']['master_credentials'],
            'cni': blue_item['conf']['config']['cni'],
            'vim_name': vim_name,
            'k8s_version': blue_item['conf']['config']['version'],
            'networks': [item['net_name'] for item in blue_item['conf']['config']['network_endpoints']['data_nets']],
            'areas': [item['id'] for item in blue_item['conf']['areas']],
            'nfvo_status': 'not_onboarded'
        })
    msg.update({'ops_type': 'add_k8s'})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.post("/kubernetes_external", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                      callbacks=callback_router.routes, summary=ADD_EXTERNAL_K8SCLUSTER_SUMMARY,
                      description=ADD_EXTERNAL_K8SCLUSTER)
async def add_external_k8scluster(cluster: K8sModelCreateFromExternalCluster):
    msg = cluster.dict()
    msg.update({'ops_type': 'add_k8s'})

    msg.update({'provided_by': 'external'})
    topology_msg_queue.put(msg)

    return {'id': 'topology'}


@topology_router.put(
    "/kubernetes/{cluster_id}",
    response_model=RestAnswer202,
    status_code=status.HTTP_202_ACCEPTED,
    callbacks=callback_router.routes)
async def update_k8scluster(cluster_updates: K8sModelUpdateRequest, cluster_id):
    msg = cluster_updates.dict()

    # check if the cluster exists in the topology
    topology = Topology.from_db(db, nbiUtil, topology_lock)
    candidate_cluster = next((item for item in topology.get_k8scluster() if item['name'] == cluster_id), None)
    if not candidate_cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail='Kubernetes cluster {} cannot be found in the topology'
                            .format(cluster_id))

    msg.update({'ops_type': 'update_k8s'})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.delete(
    "/kubernetes/{cluster_id}",
    response_model=RestAnswer202,
    status_code=status.HTTP_202_ACCEPTED,
    callbacks=callback_router.routes
)
async def delete_k8scluster(cluster_id: str):
    return produce_msg_worker('kubernetes', cluster_id, 'del_k8s')


@topology_router.get("/kubernetes", response_model=List[K8sModel])
async def get_k8scluster():
    topology = Topology.from_db(db, nbiUtil, topology_lock)
    return topology.get_k8scluster()