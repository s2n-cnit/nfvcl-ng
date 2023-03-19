from fastapi import APIRouter, Query, HTTPException, status
from blueprints.rest_blue import ShortBlueModel, DetailedBlueModel
from rest_endpoints.rest_callback import RestAnswer202
from rest_endpoints.nfvcl_callback import callback_router
from typing import List
import datetime
import importlib
import traceback
from threading import Thread
from blueprints import BlueprintBase
from blueprints.blue_types import blueprint_types
from topology import Topology
from models.k8s import K8sModel
from .blue_models import *
from main import *
from utils import get_pods_for_k8s_namespace, get_k8s_config_from_file_content, parse_k8s_clusters_from_dict
from .rest_description import *

blue_router = APIRouter(
    prefix="/nfvcl/v1/api/blue",
    tags=["Blueprints"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


def initialize_blueprints_routers():
    """
    Load Blueprint specific routers into the general blue router. This method must be called in order to enable
    blueprint specific APIs
    """
    # !! VERY IMPORTANT
    # This piece of code is adding Blueprint specific POST and PUT methods to the router
    for b in blueprint_types:
        try:
            logger.info("exposing REST APIs for Blueprint {}".format(blueprint_types[b]['class_name']))
            BlueClass = getattr(importlib.import_module("blueprints.{}".format(blueprint_types[b]['module_name'])),
                                blueprint_types[b]['class_name'])
            # Define as methods to handle creation and modification of blueprint the 2 method in this file.
            blue_router.include_router(BlueClass.fastapi_router(create_blueprint, modify_blueprint))
        except Exception:
            logger.error(traceback.format_exc())


def get_blueprint_by_id(id_: str):
    try:
        blue = db.findone_DB("blueprint-instances", {"conf.blueprint_instance_id": id_})
    except Exception:
        logger.error(traceback.format_exc())
        logger.warn('Blue {} not found in the persistency layer'.format(id_))
        blue = None
    return blue


def delete_blueprint(blue_id):
    workers.destroy_worker(blue_id)


def instantiate_blueprint(msg, blue_id):
    day0_start = datetime.datetime.now()
    try:
        selected_blue = blueprint_types[msg["type"]]
        BlueClass = getattr(importlib.import_module(
            "blueprints." + selected_blue['module_name']), selected_blue['class_name'])
        blue = BlueClass(msg, id_=str(blue_id))
        worker_queue = workers.set_worker(blue)
        worker_queue.put({'session_id': 0, 'msg': msg, 'requested_operation': 'init'})
        blue.get_timestamp("day0_start", day0_start)
    except ValueError as err:
        print(err.args)
        logger.error(traceback.format_exc())


def update_blueprint(blue, msg, blue_id, requested_operation, session_id):
    global PrometheusMan
    worker_queue = workers.get_worker(blue_id)
    worker_queue.put({'session_id': session_id, 'msg': msg, 'requested_operation': requested_operation})


@blue_router.get("/", response_model=Union[List[ShortBlueModel], List[DetailedBlueModel]])
async def get_blueprints(
        type: Union[str, None] = Query(default=None, description="Filter blueprints by type"),
        detailed: bool = Query(default=False, description="Detailed or summarized view list")
) -> dict:
    blue_filter = {}
    if type:
        blue_filter['type'] = type
    if detailed:
        res = workers.get_blue_detailed_summary(blue_filter)
    else:
        res = workers.get_blue_short_summary(blue_filter)
    return res


@blue_router.get("/{blue_id}", response_model=Union[ShortBlueModel, DetailedBlueModel])
async def get_blueprint(
        blue_id: str,
        detailed: bool = Query(default=False, description="Detailed or summarized view list")
) -> dict:
    if detailed:
        res = workers.get_blue_detailed_summary({'id': blue_id})
    else:
        res = workers.get_blue_short_summary({'id': blue_id})
    if len(res) > 0:
        return res[0]
    else:
        data = {'status': 'error', 'resource': 'blueprint',
                'description': "Blueprint instance {} not found".format(blue_id)}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)


################################################
@blue_router.post('/', response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                  callbacks=callback_router.routes)
def create_blueprint(msg: blue_create_models):
    # Generate random ID for the blueprint
    blue_id = id_generator()

    if msg.type not in blueprint_types:
        data = {'status': 'error', 'resource': 'blueprint',
                'description': 'No Blueprints are satisfying the request. The type is not in enabled blueprint types.'}
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=data)

    logger.info("Candidate Blueprint {} selected".format(blueprint_types[msg.type]['class_name']))
    # start async operations
    thread = Thread(target=instantiate_blueprint, args=(msg.dict(), blue_id,))
    # thread.daemon = True
    thread.start()
    # reply with submitted code
    return RestAnswer202(id=blue_id, resource="blueprint", operation="create", status="submitted")


@blue_router.put('/{blue_id}', response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                 callbacks=callback_router.routes)
def modify_blueprint(msg: blue_day2_models, blue_id: str):
    """
    This method is actually handling all requested operations on blueprints though NFVCL APIs.
    It receives the message and create a thread for the relative plueprint (if it does exist) to handle the request.
    """
    # assign a session id
    session_id = id_generator()
    try:
        blue = BlueprintBase.from_db(blue_id)
    except Exception:
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'blueprint',
                'description': "Blueprint instance {} not found".format(blue_id)}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)

    if msg.operation not in blue.get_supported_operations():
        logger.error('operation {} not supported by blueprint {} --> get_supported_operations(): {}'
                     .format(msg.operation, blue.get_id(), blue.get_supported_operations()))
        data = {'operation': msg.operation, 'status': 'error', 'resource': 'blueprint',
                'id': blue.get_id(), 'session_id': session_id, 'description': 'operation not supported'}
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail=data)

    thread = Thread(target=update_blueprint, args=(blue, msg, blue_id, msg.operation, session_id,))
    # thread.daemon = True
    thread.start()
    return RestAnswer202(id=blue_id, resource="blueprint", operation=msg.operation, status="submitted",
                         session_id=session_id, description="operation submitted")


@blue_router.delete('/{blue_id}', response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED,
                    callbacks=callback_router.routes)
def delete(blue_id: str):
    session_id = id_generator()
    try:
        blue = get_blueprint_by_id(blue_id)
        if not blue:
            raise ValueError('blueprint {} not found in the persistency layer'.format(blue_id))
    except Exception:
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'blueprint',
                'description': "Blueprint instance {} not found".format(blue_id)}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)

    thread = Thread(target=delete_blueprint, args=(blue_id,))
    # thread.daemon = True
    thread.start()
    return RestAnswer202(id=blue_id, resource="blueprint", operation="delete", status="submitted",
                         session_id=session_id, description="operation submitted")


@blue_router.get('/{blue_id}/pods', response_model=dict, status_code=status.HTTP_202_ACCEPTED,
                 description=BLUE_GET_PODS_DESCRIPTION,
                 summary=BLUE_GET_PODS_SUMMARY)
def get_pods(blue_id: str):
    # TODO replace all common code with a static method
    session_id = id_generator()
    try:
        blue = get_blueprint_by_id(blue_id)
        if not blue:
            raise ValueError('blueprint {} not found in the persistency layer'.format(blue_id))
    except Exception:
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'blueprint',
                'description': "Blueprint instance {} not found".format(blue_id)}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data, session_id=session_id)

    topology = Topology.from_db(db, nbiUtil, topology_lock)

    k8s_list = topology.get_k8scluster()

    k8s_clusters: List[K8sModel] = parse_k8s_clusters_from_dict(k8s_list)

    # TODO what if there are multiple k8s clusters?
    if len(k8s_clusters) > 0:
        k8s_config = get_k8s_config_from_file_content(k8s_clusters[0].credentials)
        pod_list = get_pods_for_k8s_namespace(k8s_config, namespace=blue_id)
    else:
        raise ValueError("The are NO k8s cluster in the topology!")

    to_return = pod_list.to_dict()

    return to_return
