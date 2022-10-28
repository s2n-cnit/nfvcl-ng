from fastapi import APIRouter, Query, HTTPException
from models.rest_topology import TopologyModel, VimModel, NetworkModel, RouterModel, UpdateVimModel, PduModel, K8sModel
from models.rest_callback import RestAnswer202, CallbackRequest
from rest_endpoints.nfvcl_callback import callback_router
from topology.topology import Topology, topology_msg_queue, topology_lock
from main import db, nbiUtil
from pydantic import AnyHttpUrl
from typing import Union, List

topology_router = APIRouter(
    prefix="/topology",
    tags=["Topology"],
    responses={404: {"description": "Not found"}},
)


def produce_msg_worker(resource_type: str, resource_id: str, resource_ops: str, msg_body: Union[dict, None] = None):
    topology = Topology.from_db(db, nbiUtil, topology_lock)
    if resource_type in topology.get():
        try:
            obj = next(item for item in topology.get()[resource_type] if item['name'] == resource_id)
        except StopIteration:
            raise HTTPException(status_code=404, detail="[{}] {} not found".format(resource_type, resource_id))
        if not msg_body:
            msg_body = obj
        msg_body.update({'ops_type': resource_ops})

        topology_msg_queue.put(msg_body)
        return {'id': 'topology'}

    raise HTTPException(status_code=400, detail="Topology not initialized")


def get_topology_item(resource_type, resource_id):
    topology = Topology.from_db(db, nbiUtil, topology_lock)
    if resource_type in topology.get():
        try:
            obj = next(item for item in topology.get()[resource_type] if item['name'] == resource_id)
            return obj
        except StopIteration:
            raise HTTPException(status_code=404, detail="[{}] {} not found".format(resource_type, resource_id))

    raise HTTPException(status_code=400, detail="Topology not initialized")


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


@topology_router.post("/", response_model=RestAnswer202, status_code=202, callbacks=callback_router.routes)
async def create_topology(
        topo: TopologyModel,
        terraform: bool = Query(default=False,
                                description="set to true if you want to terraform VIMs upon topology creation"),
        ):
    msg = topo.dict()
    msg.update({'ops_type': 'add_topology', 'terraform': terraform})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.delete("/", response_model=RestAnswer202, status_code=202, callbacks=callback_router.routes)
async def delete_topology(
        msg_body: CallbackRequest,
        terraform: bool = Query(default=False,
                                description="set to true if you want to terraform VIMs upon topology creation")
):
    topology = Topology.from_db(db, nbiUtil, topology_lock)
    if not topology:
        raise HTTPException(status_code=404, detail="topology not declared")
    msg = msg_body.dict()
    msg.update({'ops_type': 'del_topology', 'terraform': terraform})
    print(msg)
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.get("/vim/{vim_id}", response_model=VimModel)
async def get_vim(vim_id: str):
    return get_topology_item('vims', vim_id)


@topology_router.post("/vim", response_model=RestAnswer202, status_code=202, callbacks=callback_router.routes)
async def create_vim(
        vim: VimModel,
        terraform: bool = Query(default=False,
                                description="set to true if you want to terraform VIMs upon topology creation")
):
    msg = vim.dict()
    msg.update({'ops_type': 'add_vim', 'terraform': terraform})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.put("/vim/{vim_id}", response_model=RestAnswer202, status_code=202, callbacks=callback_router.routes)
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
    status_code=202,
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


@topology_router.post("/network", response_model=RestAnswer202, status_code=202, callbacks=callback_router.routes)
async def create_network(network: NetworkModel):
    msg = network.dict()
    msg.update({'ops_type': 'add_net'})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.delete(
    "/network/{network_id}",
    response_model=RestAnswer202,
    status_code=202,
    callbacks=callback_router.routes
)
async def delete_network(network_id: str):
    return produce_msg_worker('networks', network_id, 'del_net')


@topology_router.get("/router/{router_id}", response_model=RouterModel)
async def get_router(router_id: str):
    return get_topology_item('routers', router_id)


@topology_router.post("/router", response_model=RestAnswer202, status_code=202, callbacks=callback_router.routes)
async def create_router(router: RouterModel):
    msg = router.dict()
    msg.update({'ops_type': 'add_router'})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.delete(
    "/router/{router_id}",
    response_model=RestAnswer202,
    status_code=202,
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


@topology_router.post("/pdu", response_model=RestAnswer202, status_code=202, callbacks=callback_router.routes)
async def create_pdu(router: PduModel):
    msg = router.dict()
    msg.update({'ops_type': 'add_pdu'})
    topology_msg_queue.put(msg)
    return {'id': 'topology'}


@topology_router.delete(
    "/router/{router_id}",
    response_model=RestAnswer202,
    status_code=202,
    callbacks=callback_router.routes
)
async def delete_router(router_id: str):
    return produce_msg_worker('pdus', router_id, 'del_pdu')
