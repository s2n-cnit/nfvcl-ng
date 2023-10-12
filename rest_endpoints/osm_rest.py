from typing import List
from fastapi import APIRouter, status
from nfvo.osm_nbi_util import get_osm_nbi_utils

osm_utils = get_osm_nbi_utils()

osm_router = APIRouter(
    prefix="/v1/osm",
    tags=["OSM"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@osm_router.delete("/delete_all_vnfd", response_model=List[bool])
async def delete_all_vnfd() -> List[bool]:
    """
    Deletes all VNFD on OSM (when not used by NSD or active VNF). This function is useful when NFVCL fails to remove
    them from OSM.
    """
    vnfd_list = osm_utils.get_vnfd_list()
    responses = []
    for vnfd in vnfd_list:
        responses.append(osm_utils.delete_vnfd(vnfd['_id']))
    return responses


@osm_router.delete("/delete_all_nsd", response_model=List[dict])
async def delete_all_nsd() -> List[dict]:
    """
    Deletes all NSD on OSM (when not used by NS). This function is useful when NFVCL fails to remove them from OSM.
    """
    nsd_list: dict = osm_utils.get_nsd_list()
    responses = []
    for nsd in nsd_list:
        responses.append(osm_utils.nsd_delete(nsd['_id']))
    return responses
