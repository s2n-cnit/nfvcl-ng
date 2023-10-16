from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from models.config_model import NFVCLConfigModel
from nfvo.osm_nbi_util import get_osm_nbi_utils
from rest_endpoints.nfvcl_callback import callback_router
from utils.helm_repository import helm_repo, chart_path, helm_url_prefix
from rest_endpoints.helm_model import HelmRepo
from utils.log import create_logger
import json
import os
from utils.util import get_nfvcl_config

nbiUtil = get_osm_nbi_utils()
nfvcl_config: NFVCLConfigModel = get_nfvcl_config()
# The repo name must NOT contain underscores _, upper case
HELM_REPO_NAME = "nfvcl"


helm_router = APIRouter(
    prefix="/helm_repo",
    tags=["Helm repository"],
    responses={404: {"description": "Not found"}},
)
logger = create_logger('Helm REPO REST endpoint')

@helm_router.get("/{chart_type}/{chart_file}")
def helm_repo_get(chart_type, chart_file):
    logger.debug("GET REQUEST for type " + chart_type + " with id " + chart_file)
    if chart_type == "charts":
        if os.path.isfile(chart_path + "charts/" + chart_file):
            return FileResponse(chart_path + "charts/" + chart_file, media_type='application/octet-stream',
                                filename=chart_file)
        else:
            raise HTTPException(status_code=404, detail="Resource not found")
    raise HTTPException(status_code=400, detail="[NFVCL_DAY2] Operation not supported")


@helm_router.get("/{file}")
def helm_index_get(file):
    logger.debug("GET REQUEST for helm index.yaml")
    if file == "index.yaml":
        if not os.path.isfile(chart_path + "index.yaml"):
            logger.info("recreating the helm repo index")
            helm_repo.create_index()
        return FileResponse(chart_path + "index.yaml", media_type='application/yaml', filename="index.yaml")
    raise HTTPException(status_code=400, detail="[NFVCL_HELM_REPO] Operation not supported")


@helm_router.post("/", status_code=204, callbacks=callback_router.routes)
def helm_onboard_post(helm_repo_item: HelmRepo):
    logger.debug("GET POST for helm repository index")
    helm_repo_dict = helm_repo_item.model_dump()
    try:
        helm_repo.set_entry(helm_repo_dict)
    except Exception as e:
        raise HTTPException(status_code=404, detail=json.dumps(e))


@helm_router.on_event("startup")
def create_helm_repo():
    """
    On startup, it adds to OSM the internal chart repo of the NFVCL. In this way OSM can use custom charts to deploy
    KDUs
    """
    # Adding Helm repository to OSM
    r = next((item for item in nbiUtil.get_k8s_repos() if item['name'] == HELM_REPO_NAME), None)
    logger.info('checking existing helm repo: {}'.format(r))
    if r is not None:
        logger.info('Deleting previous helm repository')
        nbiUtil.delete_k8s_repo(HELM_REPO_NAME)

    # The repo name must not contain underscores _
    r = nbiUtil.add_k8s_repo(HELM_REPO_NAME, "http://{}:{}{}".format(nfvcl_config.nfvcl.ip, nfvcl_config.nfvcl.port, helm_url_prefix))
    logger.debug('Adding helm repo result: {}'.format(r))
