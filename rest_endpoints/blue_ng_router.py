from typing import List, Optional
from fastapi import APIRouter, Query, status, Request
from blueprints_ng.lcm.blueprint_manager import BlueprintManager
from models.blueprint_ng.worker_message import WorkerMessageType
from models.response_model import OssCompliantResponse, OssStatus
from rest_endpoints.nfvcl_callback import callback_router
from utils.log import create_logger

blue_ng_router = APIRouter(
    prefix="/nfvcl/v2/api/blue",
    tags=["Blueprints NG"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

logger = create_logger("BLUE NG ROUTER")

__blueprint_manager: BlueprintManager | None = None

def get_blueprint_manager() -> BlueprintManager:
    """
    Allow to retrieve the BlueprintManager (that can have only one instance)
    Returns:
        The blueprint manager
    """
    global __blueprint_manager
    if __blueprint_manager is not None:
        return __blueprint_manager
    else:
        __blueprint_manager = BlueprintManager(blue_ng_router, create_blueprint, update_blueprint)
        return __blueprint_manager

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


def create_blueprint(msg: dict, request: Request):
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
    blue_id = blue_man.create_blueprint(msg, blue_type)
    return OssCompliantResponse(status=OssStatus.deploying, detail=f"Blueprint {blue_id} is being deployed...")


def update_blueprint(msg: dict, blue_id: str, request: Request):
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
    blue_worker.put_message(WorkerMessageType.DAY2, path, msg)
    return OssCompliantResponse(status=OssStatus.processing, detail=f"Blueprint day2 message for {blue_id} given to the worker...")

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


@blue_ng_router.delete('/all/blue', response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                    callbacks=callback_router.routes)
def delete_all_blueprints():
    blue_man = get_blueprint_manager()
    blue_man.delete_all_blueprints()
    return OssCompliantResponse(status=OssStatus.processing, detail=f"Blueprints are being delete...")
