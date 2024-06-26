from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from nfvcl.models.config_model import NFVCLConfigModel
from nfvcl.utils.helm_repository import CHART_PATH, REPO_PATH, setup_helm_repo
from nfvcl.utils.log import create_logger
import os
from nfvcl.utils.util import get_nfvcl_config

nfvcl_config: NFVCLConfigModel = get_nfvcl_config()

helm_router = APIRouter(
    prefix="/helm_repo",
    tags=["Helm repository"],
    responses={404: {"description": "Not found"}},
)
logger = create_logger('Helm REPO REST')

@helm_router.get("/charts/{chart_file}")
def helm_repo_get(chart_file):
    """
    Allow downloading a chart package from the NFVCL repo

    Args:
        chart_file: the name of the .tgz packages. Use '/charts' to get a file list

    Returns:
        The file to be downloaded
    """
    logger.debug("GET REQUEST for with id " + chart_file)
    if os.path.isfile(CHART_PATH + chart_file):
        return FileResponse(CHART_PATH + chart_file, media_type='application/octet-stream',
                            filename=chart_file)
    else:
        raise HTTPException(status_code=404, detail="Resource not found")


@helm_router.get("/charts")
def helm_repo_get_file_list() -> List[str]:
    """
    Retrieve a file list of the available charts.
    """
    if os.path.isdir(CHART_PATH):
        return os.listdir(CHART_PATH)
    else:
        raise HTTPException(status_code=404, detail="Resource not found")


@helm_router.get("/index.yaml")
def helm_index_get():
    """
    Allow downloading the index file of the HELM REPO.
    """
    logger.debug("GET REQUEST for helm index.yaml")
    if not os.path.isfile(REPO_PATH + "index.yaml"):
        logger.info("Recreating the helm repo index")
        setup_helm_repo()
    return FileResponse(REPO_PATH + "index.yaml", media_type='application/yaml', filename="index.yaml")
