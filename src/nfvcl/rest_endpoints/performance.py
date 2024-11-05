from fastapi import APIRouter
from nfvcl.blueprints_ng.lcm.performance_manager import get_performance_manager

from nfvcl.utils.log import create_logger


performance_router = APIRouter(
    prefix="/performance",
    tags=["Performance API"],
    responses={404: {"description": "Not found"}},
)

logger = create_logger('Performance API')

performance_manager = get_performance_manager()

@performance_router.get("/blue/{blueprint_id}", status_code=200)
def get(blueprint_id: str):
    return performance_manager.get_blue_performance(blueprint_id)
