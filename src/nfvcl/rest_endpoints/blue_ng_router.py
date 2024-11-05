import typing
from functools import partial
from typing import List, Optional, Callable

import httpx
from fastapi import APIRouter, Query, status, Request

from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG
from nfvcl.blueprints_ng.lcm.blueprint_manager import get_blueprint_manager
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.utils import clone_function_and_patch_types
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint_ng.worker_message import WorkerMessageType, BlueprintOperationCallbackModel
from nfvcl.models.http_models import HttpRequestType
from nfvcl.models.response_model import OssCompliantResponse, OssStatus
from nfvcl.rest_endpoints.nfvcl_callback import callback_router
from nfvcl.utils.log import create_logger

blue_ng_router = APIRouter(
    prefix="/nfvcl/v2/api/blue",
    tags=["Blueprints NG"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

logger = create_logger("BLUE NG ROUTER")

class BlueprintNGFunction(NFVCLBaseModel):
    path: str
    bound_method: Callable
    rest_method: List[str]

def add_fake_endpoints(cls: BlueprintNG, prefix: str) -> List[BlueprintNGFunction]:
    """
    Initialize the blueprint router and register apis to it.
    Args:
        cls: Bluprint class
        prefix: The prefix that all the APIs declared in the blueprint will have.

    Returns:
        The created and configured router.
    """
    function_list: List[BlueprintNGFunction] = []

    setattr(cls, "patched_create", classmethod(clone_function_and_patch_types(create_blueprint, {"msg": next(iter(typing.get_type_hints(cls.create).values()))}, doc=cls.create.__doc__)))
    function_list.append(BlueprintNGFunction(path=f"", bound_method=getattr(cls, "patched_create"), rest_method=["POST"]))

    # The prefix is the base path of the module, e.g., 'api_common_url/vyos/create' -> prefix = 'vyos'
    for day2_route in blueprint_type.get_module_routes(prefix):
        type_overrides = {}
        if len(typing.get_type_hints(day2_route.function)) > 0:
            type_overrides["msg"] = next(iter(typing.get_type_hints(day2_route.function).values()))
        patched_name = f"patched_{day2_route.function.__name__}"
        if HttpRequestType.GET in day2_route.methods:
            setattr(cls, patched_name, classmethod(clone_function_and_patch_types(get_from_blueprint, type_overrides, doc=day2_route.function.__doc__)))
        else:
            setattr(cls, patched_name, classmethod(clone_function_and_patch_types(update_blueprint, type_overrides, doc=day2_route.function.__doc__)))
        function_list.append(BlueprintNGFunction(path=f"{day2_route.final_path}", bound_method=getattr(cls, patched_name), rest_method=day2_route.get_methods_str()))
        # print("GenericItem[str]:", inspect.signature(getattr(cls, patched_name)))
    return function_list

def setup_blueprints_routers():
    for module in blueprint_type.get_registered_modules().values():
        module_router = APIRouter(
            prefix=f"/{module.path}",
            tags=[f"Blueprints NG - {module.class_name}"],
            responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
        )
        for function in add_fake_endpoints(module.blue_class, module.path):
            module_router.add_api_route(function.path, function.bound_method, methods=function.rest_method)
        blue_ng_router.include_router(module_router)

def get_callback_function(request: Request):
    """
    Generate a callback function
    Args:
        request: The HTTP request that may contain a 'callback' query parameter.

    Returns: Generated callback function
    """
    callback_function = None
    if "callback" in request.query_params:
        callback_url = request.query_params["callback"]
        callback_function = partial(call_callback_url, callback_url)
    return callback_function

def call_callback_url(url: str, msg: BlueprintOperationCallbackModel):
    """
    Function that make the request to the callback url
    """
    logger.debug(f"Calling callback url: {url}, msg: {msg}")
    try:
        httpx.post(url, json=msg.model_dump_json(exclude_none=True))
    except Exception as e:
        logger.error(f"Error calling callback: {str(e)}")

@blue_ng_router.get("/", response_model=List[dict])
async def get_blueprints(blue_type: Optional[str] = Query(default=None), detailed: bool = Query(default=False)) -> List[dict]:
    """
    Return the list of deployed blueprints.

    Args:
        blue_type: The type, used to filter the list.
        detailed: If true, return all the info saved in the database about the blueprints.

    Returns:
        The list of blueprints.
    """
    blue_man = get_blueprint_manager()
    return blue_man.get_blueprint_summary_list(blue_type, detailed=detailed)


@blue_ng_router.get("/{blueprint_id}", response_model=dict)
async def get_blueprint(blueprint_id: str, detailed: bool = Query(default=False)):
    """
    Return the details of a blueprint, given the ID.

    Args:
        blueprint_id: The ID of the blueprint
        detailed: If true, return all the info saved in the database about the blueprint.

    Returns:
        The summary/details of the blueprint

    Raises:
        BlueprintNotFoundException if blueprint does not exist
    """
    blue_man = get_blueprint_manager()
    return blue_man.get_blueprint_summary_by_id(blueprint_id=blueprint_id, detailed=detailed)


def create_blueprint(cls, msg: dict, request: Request):
    """
    Deploy a new blueprint in the NFVCL.
    This function receives ALL the creation requests of all the blueprints!

    Args:
        msg: The message of creation, the type depends on the blueprint type.
        request: The details about the request, used to retrieve the path, can be used for request info.

    Returns:
        A OssCompliantResponse telling the user if the request has been accepted or not.
    """
    blue_man = get_blueprint_manager()
    blue_type = request.url.path.split('/')[-1]
    blue_id = blue_man.create_blueprint(msg, blue_type, callback=get_callback_function(request))
    return OssCompliantResponse(status=OssStatus.deploying, detail=f"Blueprint {blue_id} is being deployed...")


def update_blueprint(cls, msg: dict, blue_id: str, request: Request):
    """
    Update an existing blueprint in the NFVCL (day 2 request).
    This function receives ALL the update (day2) requests of all the blueprints!

    Args:
        msg: Day 2 message, the type depends on the blueprint type.
        blue_id (str): The ID of the blueprint to be updated.
        request: The details about the request, used to retrieve the path, can be used for request info.

    Returns:
        A OssCompliantResponse telling the user if the request has been accepted or not.
    """
    blue_man = get_blueprint_manager()
    path = "/".join(request.url.path.split('/')[-2:]) # Takes only the last 2 paths "abc/bcd/fde/have" -> fde/have
    blue_worker = blue_man.get_worker(blue_id)
    blue_worker.put_message(WorkerMessageType.DAY2, path, msg, callback=get_callback_function(request))
    return OssCompliantResponse(status=OssStatus.processing, detail=f"Blueprint day2 message for {blue_id} given to the worker...")

def get_from_blueprint(cls, blue_id: str, request: Request):
    """
    Get data from an existing blueprint in the NFVCL (day 2 request).
    This function receives ALL get (day2) requests of all the blueprints!

    Args:
        blue_id (str): The ID of the blueprint from which the data will be retrieved.
        request: The details about the request, used to retrieve the path, can be used for request info.

    Returns:
        The response for the request
    """
    blue_man = get_blueprint_manager()
    path = "/".join(request.url.path.split('/')[-2:]) # Takes only the last 2 paths "abc/bcd/fde/have" -> fde/have
    blue_worker = blue_man.get_worker(blue_id)
    response = blue_worker.put_message_sync(WorkerMessageType.DAY2, path, {})
    return response

@blue_ng_router.delete('/{blueprint_id}', response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED, callbacks=callback_router.routes)
def delete(blueprint_id: str):
    """
    Deletes a blueprint from the NFVCL. Delete the instances deployed on the VIMs.

    Args:
        blueprint_id: The ID of the blueprint to be deleted.

    Returns:
        A OssCompliantResponse telling the user if the request has been accepted or not.
    """
    blue_man = get_blueprint_manager()
    blue_man.delete_blueprint(blueprint_id)
    return OssCompliantResponse(status=OssStatus.processing, detail=f"Blueprint deletion message for {blueprint_id} given to the worker...")


@blue_ng_router.delete('/all/blue', response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED, callbacks=callback_router.routes)
def delete_all_blueprints():
    """
    Deletes all blueprints
    """
    blue_man = get_blueprint_manager()
    blue_man.delete_all_blueprints()
    return OssCompliantResponse(status=OssStatus.processing, detail=f"Blueprints are being deleted...")


@blue_ng_router.patch('/protect/{blueprint_id}', response_model=dict, status_code=status.HTTP_202_ACCEPTED, callbacks=callback_router.routes)
def protect_blueprint(blueprint_id: str, protect: bool):
    blue_man = get_blueprint_manager()
    worker = blue_man.get_worker(blueprint_id=blueprint_id)
    worker.protect_blueprint(protect)
    return blue_man.get_blueprint_summary_by_id(blueprint_id=blueprint_id, detailed=False)
