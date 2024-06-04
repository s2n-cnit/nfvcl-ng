from typing import List
from fastapi import APIRouter, status
from requests import Response
from nfvcl.models.vim import VimModel
from nfvcl.rest_endpoints.rest_callback import RestAnswer202
from nfvcl.topology.topology import Topology
from nfvcl.config_templates.openstack.image_manager import get_nfvcl_image_list
from nfvcl.models.openstack.images import ImageList
from nfvcl.utils.openstack.openstack_client import OpenStackClient
from nfvcl.main import db, nbiUtil, topology_lock

openstack_router = APIRouter(
    prefix="/v1/openstack",
    tags=["OS"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


@openstack_router.post("/update_images", response_model=RestAnswer202)
async def update_images():
    """
    Updates all images needed used for deploying blueprints. The operation in done on all VIMs belonging to the topology.
    If already present, images are removed and then added to the single VIM.
    Image is downloaded from a URL, the procedure can be slow before all images are ready on the VIM.
    """
    topo = Topology.from_db(db, nbiUtil, topology_lock)
    vims: List[VimModel] = topo.get_model().get_vims()
    image_list: ImageList = get_nfvcl_image_list()

    for vim in vims:
        client = OpenStackClient(vim)
        for image in image_list.images:
            if image.to_download is False:
                continue  # Skip the deletion and download if manual operation is needed

            found_image = client.find_image(image.name)

            if found_image is not None:
                client.delete_image(found_image)

            created_image: Response = client.create_and_download_image(image)

    return RestAnswer202(id='VIM', operation_type="VIM images upload")
