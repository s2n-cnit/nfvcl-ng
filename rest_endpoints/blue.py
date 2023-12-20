from typing import List

from blueprints.blue_5g_base.blueprint_5g_base_beta import Blue5GBaseBeta
from fastapi import APIRouter, Query, HTTPException, status
from blueprints.blueprint_beta import BlueprintBaseBeta
from models.blueprint.blue_events import BlueEventType
from models.blueprint.blueprint_base_model import BlueprintVersion
from models.blueprint.rest_blue import BlueGetDataModel
from models.event import Event
from models.response_model import OssCompliantResponse, OssStatus
from rest_endpoints.rest_callback import RestAnswer202
from rest_endpoints.nfvcl_callback import callback_router
import datetime
import importlib
import traceback
from threading import Thread
from blueprints import BlueprintBase
from models.blueprint.blue_types import blueprint_types
from topology.topology import Topology
from models.k8s.topology_k8s_model import K8sModel
from .blue_models import *
from main import old_workers, db, persistency, id_generator, nbiUtil, topology_lock, workers
from utils.k8s import get_pods_for_k8s_namespace, get_k8s_config_from_file_content, parse_k8s_clusters_from_dict
from utils.log import create_logger
from .rest_description import *
from utils.redis_utils.redis_manager import get_redis_instance, trigger_redis_event
from utils.redis_utils.topic_list import BLUEPRINT
from pymongo.cursor import Cursor

blue_router = APIRouter(
    prefix="/nfvcl/v1/api/blue",
    tags=["Blueprints"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

logger = create_logger("BLUE")


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
        logger.warning('Blue {} not found in the persistency layer'.format(id_))
        blue = None
    return blue


def get_all_blueprint() -> Cursor:
    """
    Return a list of all the blueprints.
    Returns:
        a mongo cursor that can be iterated.
    """
    try:
        blues = db.find_DB("blueprint-instances", None)
    except Exception:
        logger.error(traceback.format_exc())
    return blues


def get_blueprint_model_by_id(blueprint_id: str):
    """
    Returns the parsed model of the blueprint from the database
    Args:
        blueprint_id: The ID of the blueprint to be retrieved

    Returns:
        The parsed blueprint from the database
    """
    try:
        db_data = db.findone_DB("blueprint-instances", {"id": blueprint_id})
        if not db_data:
            raise ValueError('Blueprint {} not found in DB or malformed'.format(blueprint_id))
        if 'type' in db_data:
            selected_blue = blueprint_types[db_data["type"]]
            BlueClass = getattr(importlib.import_module(
                "blueprints." + selected_blue['module_name']), selected_blue['class_name'])

            return BlueClass(db_data['conf'], id_=str(blueprint_id))
        else:
            raise ValueError('Blueprint {} type not found in DB'.format(blueprint_id))
    except Exception:
        logger.error(traceback.format_exc())
        err_msg = 'Blue {} not found in the persistency layer'.format(blueprint_id)
        logger.warning(err_msg)
        raise ValueError(err_msg)
    return None


def delete_blueprint(blue_id):
    """
    Remove a blueprint from the NVFCL
    Args:
        blue_id: The ID of the blueprint to be deleted, together with its NSs.
    """
    _db = persistency.DB()
    db_data = _db.findone_DB("blueprint-instances", {'id': blue_id})
    if not db_data:
        raise ValueError('blueprint {} not found in DB or malformed'.format(blue_id))

    # IF blueprint V1 or V2 we need to take it from different queues
    if 'version' in db_data:
        if db_data['version'] == BlueprintVersion.ver2_00.value:
            workers.destroy_worker(blue_id)
        if db_data['version'] == BlueprintVersion.ver1_00.value:
            old_workers.destroy_worker(blue_id)
    else:
        # If no version, supposing old blueprint
        old_workers.destroy_worker(blue_id)


def instantiate_blueprint(msg, blue_id):
    day0_start = datetime.datetime.now()
    try:
        selected_blue = blueprint_types[msg["type"]]
        BlueClass = getattr(importlib.import_module(
            "blueprints." + selected_blue['module_name']), selected_blue['class_name'])
        blue = BlueClass(msg, id_=str(blue_id))
        trigger_redis_event(get_redis_instance(), BLUEPRINT,
                            Event(operation=BlueEventType.BLUE_CREATE.value, data={"blue_id": blue_id}))

        # Checking if the instance is coming from OLD or NEW blueprint base
        if issubclass(BlueClass, BlueprintBaseBeta):
            # worker_queue is composed by NEW type of worker
            worker_queue = workers.set_worker(blue)
            worker_queue.put({'session_id': 0, 'msg': msg, 'requested_operation': 'init'})
            blue.set_timestamp("day0_start", day0_start)
        else:
            worker_queue = old_workers.set_worker(blue)
            worker_queue.put({'session_id': 0, 'msg': msg, 'requested_operation': 'init'})
            blue.get_timestamp("day0_start", day0_start)
    except ValueError as err:
        print(err.args)
        logger.error(traceback.format_exc())


def update_blueprint(msg, blue_id, requested_operation, session_id, version: BlueprintVersion):
    if version == BlueprintVersion.ver1_00:
        worker_queue = old_workers.get_worker(blue_id)
        worker_queue.put({'session_id': session_id, 'msg': msg, 'requested_operation': requested_operation})
    elif version == BlueprintVersion.ver2_00:
        worker_queue = workers.get_worker(blue_id)
        worker_queue.put({'session_id': session_id, 'msg': msg, 'requested_operation': requested_operation})


@blue_router.get("/", response_model=List[dict])
async def get_blueprints(
    type: Union[str, None] = Query(default=None, description="Filter blueprints by type"),
    detailed: bool = Query(default=False, description="Detailed or summarized view list")
) -> List[dict]:
    blue_filter = {}
    if type:
        blue_filter['type'] = type
    if detailed:
        res = old_workers.get_blue_detailed_summary(blue_filter)
        to_ret = [item.model_dump() for item in res]
    else:
        res = old_workers.get_blue_short_summary(blue_filter)
        to_ret = [item.model_dump() for item in res]

    return to_ret


@blue_router.get("/{blue_id}", response_model=dict)
async def get_blueprint(
    blue_id: str,
    detailed: bool = Query(default=False, description="Detailed or summarized view list")
) -> dict:
    if detailed:
        res = old_workers.get_blue_detailed_summary({'id': blue_id})
    else:
        res = old_workers.get_blue_short_summary({'id': blue_id})
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
    thread = Thread(target=instantiate_blueprint, args=(msg.model_dump(), blue_id,))
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
        # Looking if blueprint is version 1 or 2
        _db = persistency.DB()
        db_data = _db.findone_DB("blueprint-instances", {'id': blue_id})
        if not db_data:
            raise ValueError('blueprint {} not found in DB or malformed'.format(blue_id))

        version: BlueprintVersion = BlueprintVersion.ver1_00
        if 'version' in db_data:
            if db_data['version'] == BlueprintVersion.ver2_00.value:
                version = BlueprintVersion.ver2_00
        # TODO should be BlueprintBaseBeta for v2
        blue = BlueprintBase.from_db(blue_id)  # USED ONLY FOR LOGGING PURPOSE

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

    thread = Thread(target=update_blueprint, args=(msg, blue_id, msg.operation, session_id, version))
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


@blue_router.delete('/all/blue', response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                    callbacks=callback_router.routes)
def delete_all_blueprints():
    """
    Remove all blueprints. For every blueprint, network services are deleted from VIMs and K8s clusters (by OSM)
    """
    try:
        blues = get_all_blueprint()
        if not blues:
            raise ValueError('Blueprints not found in the persistency layer')
    except Exception:
        return OssCompliantResponse(status=OssStatus.failed, detail="")

    # For each blueprint we start to remove it.
    for blue in blues:
        thread = Thread(target=delete_blueprint, args=(blue['id'],))
        thread.start()

    return OssCompliantResponse(detail="Operation submitted")


@blue_router.get('/{blue_id}/get_data', response_model=dict)
def get_data_from_blue(blue_id: str, request: BlueGetDataModel):
    """
    This API allow to retrieve data directly from a blueprint. It loads the model from the database and allow to obtain
    specific data, depending on the blueprint.
    The request changes depending on the blueprint and on the type of request

    Args:
        blue_id: The ID of the blueprint

        request: The request that contains the type of request and arguments to be given at the blueprint to elaborate
        the response. The content of arguments change on blueprint basis and on the type of request. A wrong request
        should return the arguments SCHEMA.

    Returns:
        The desired data or the correct schema in case of wrong request.
    """
    try:
        blueprint = get_blueprint_model_by_id(blue_id)

        if blueprint.__class__.__bases__[0] == BlueprintBaseBeta:
            return blueprint.get_data(request)
        else:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Operation supported only for "
                                                                                    "blueprint 2.0 version")
    except ValueError as val_err:
        logger.error(str(val_err))
        data = {'status': 'error', 'resource': 'blueprint',
                'description': str(val_err)}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)
    except Exception as e:
        logger.error(str(e))
        data = {'status': 'error', 'resource': 'blueprint',
                'description': str(e)}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data)


@blue_router.get('/{blue_id}/pods', response_model=dict, status_code=status.HTTP_202_ACCEPTED,
                 description=BLUE_GET_PODS_DESCRIPTION,
                 summary=BLUE_GET_PODS_SUMMARY)
def get_pods(blue_id: str):
    """
    Obtain pods for a blueprint OVER ALL k8s clusters.
    Differently from get_pods in k8s management this method iterate over all k8s clusters and check if there are
    some pods in a namespace that have the same name of the blueprint

    Args:

        blue_id: the blueprint ID of pods we are looking for.

    Returns:
        The list of pods
    """
    # TODO replace all common code with a static method
    local_session_id = id_generator()
    try:
        blue = get_blueprint_by_id(blue_id)
        if not blue:
            raise ValueError('blueprint {} not found in the persistency layer'.format(blue_id))
    except Exception:
        # Print on the console
        logger.error(traceback.format_exc())
        data = {'status': 'error', 'resource': 'blueprint',
                'description': "Blueprint instance {} not found".format(blue_id)}
        # Inform the API caller
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=data)

    topology = Topology.from_db(db, nbiUtil, topology_lock)

    k8s_clusters: List[K8sModel] = topology.get_k8s_clusters()

    # TODO test code
    pods_for_cluster: dict = {}
    if len(k8s_clusters) > 0:
        for k8s_instance in k8s_clusters:
            k8s_config = get_k8s_config_from_file_content(k8s_clusters[0].credentials)
            # Getting all pods in namespace that correspond to the blueprint ID
            pod_list = get_pods_for_k8s_namespace(k8s_config, namespace=blue_id)
            pods_for_cluster[k8s_instance.name] = pod_list.to_dict()
    else:
        raise ValueError("The are NO k8s cluster in the topology!")

    to_return = pods_for_cluster

    return to_return
