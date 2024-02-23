from typing import List, Optional
from fastapi import APIRouter, Query, status, Request
from blueprints_ng.lcm.blueprint_manager import BlueprintManager
from models.blueprint_ng.worker_message import WorkerMessageType
from models.response_model import OssCompliantResponse
from rest_endpoints.nfvcl_callback import callback_router
from utils.log import create_logger

blue_ng_router = APIRouter(
    prefix="/nfvcl/v2/api/blue",
    tags=["Blueprints NG"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

logger = create_logger("BLUE NG ROUTER")

__blueprint_manager: BlueprintManager | None = None

def get_blueprint_manager():
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
async def get_blueprints(blue_type: Optional[str] = Query(default=None, description="Filter blueprints by type"), detailed: bool = Query(default=False, description="Detailed or summarized view list")) -> List[dict]:
    blue_man = get_blueprint_manager()
    return blue_man.get_blueprint_summary_list(blue_type, detailed=detailed)


@blue_ng_router.get("/{blueprint_id}", response_model=dict)
async def get_blueprint(blueprint_id: str, detailed: bool = Query(default=False, description="Detailed or summarized view list")):
    blue_man = get_blueprint_manager()
    return blue_man.get_blueprint_summary_by_id(blueprint_id=blueprint_id, detailed=detailed)


def create_blueprint(msg: dict, request: Request):
    blue_man = get_blueprint_manager()
    blue_type = request.url.path.split('/')[-1]
    blue_id = blue_man.create_blueprint(msg, blue_type)
    return OssCompliantResponse(detail=f"Blueprint {blue_id} created")


def update_blueprint(msg: dict, blue_id: str, request: Request):
    blue_man = get_blueprint_manager()
    path = "/".join(request.url.path.split('/')[-2:]) # Takes only the last 2 paths "abc/bcd/fde/have" -> fde/have
    blue_worker = blue_man.get_worker(blue_id)
    blue_worker.put_message(WorkerMessageType.DAY2, path, msg)
    return OssCompliantResponse(detail=f"Blueprint message to {blue_id} given to the worker.")

@blue_ng_router.delete('/{blue_id}', response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED, callbacks=callback_router.routes)
def delete(blue_id: str):
    blue_man = get_blueprint_manager()
    blue_worker = blue_man.get_worker(blue_id)
    blue_worker.destroy_blueprint()
    return OssCompliantResponse(detail=f"Blueprint message to {blue_id} given to the worker.")


@blue_ng_router.delete('/all/blue', response_model=OssCompliantResponse, status_code=status.HTTP_202_ACCEPTED,
                    callbacks=callback_router.routes)
def delete_all_blueprints():
    pass
