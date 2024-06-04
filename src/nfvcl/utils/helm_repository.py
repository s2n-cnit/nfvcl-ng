from typing import List
from nfvcl.models.config_model import NFVCLConfigModel
from nfvcl.models.helm.helm_model import HelmChart, HelmIndex
from nfvcl.nfvo.osm_nbi_util import get_osm_nbi_utils
from nfvcl.utils.log import create_logger
import yaml
import os.path
import hashlib

from nfvcl.utils.persistency import DB
from nfvcl.utils.util import get_nfvcl_config

nbiUtil = get_osm_nbi_utils()
nfvcl_config: NFVCLConfigModel = get_nfvcl_config()

logger = create_logger('HelmRepository')
db = DB()
REPO_PATH = 'helm_charts/'
CHART_PATH = REPO_PATH + 'charts/'
helm_url_prefix = '/helm_repo/'
# The repo name must NOT contain underscores _, upper case
HELM_REPO_NAME = "nfvcl"

def setup_helm_repo():
    """
    Setup helm repo for NFVCL.
    """
    _create_helm_index_file(_load_helm_charts())
    _setup_osm_helm_repo()


def _load_helm_charts() -> List[HelmChart]:
    """
    Read all the files present in helm_charts/charts and build a list of HelmChart to be included in the index file.
    All files in the helm_charts folder must be named {name}-{version}.tgz.
    Name must not include '-' character.
    Version must be formatted like '0.4.2'.

    Returns:
        The list of hemlchart to be included in the index file.
    """
    chart_list = []

    try:
        file_list = os.listdir(CHART_PATH)
        #Remove useless file that was uploaded by mistake TODO remove in future version, here just for compatibility
        try:
            os.remove(CHART_PATH+'index.yaml')
        except FileNotFoundError:
            logger.debug("Useless file index was already deleted")
    except FileNotFoundError:
        logger.warning(f"The directory '{CHART_PATH}' does not exist. Creating...")
        os.mkdir(REPO_PATH)
        os.mkdir(CHART_PATH)
        file_list = []

    # For each file we build the HELM chart object
    for file in file_list:
        digest = ""
        with open(CHART_PATH + file, "rb") as f:
            file_bytes = f.read()
            digest = hashlib.sha256(file_bytes).hexdigest()

        chart_url = f'http://{nfvcl_config.nfvcl.ip}:{nfvcl_config.nfvcl.port}{helm_url_prefix}charts/{file}'

        name_no_extension = file[0:-4] # Remove .tgz (last 4 chars)
        name = name_no_extension.split('-')[0]

        if name.count('_') > 0 or any(char.isupper() for char in name):
            raise ValueError(f"The name of the helm chart contains invalid characters {name}")

        version = name_no_extension.split('-')[1]

        chart_list.append(HelmChart(name=name, version=version, digest=digest, urls=[chart_url]))

    return chart_list


def _create_helm_index_file(chart_list: List[HelmChart]):
    """
    Creates the index file for the helm repo. The index file contains the list of helm chart available in the helm repo.
    The index file is used from VNF instances to retrieve helm charts.

    Args:
        chart_list: the list of the chart to be included in the index file
    """
    helm_index = HelmIndex.build_index(chart_list)

    try:
        yaml_file = open(REPO_PATH + 'index.yaml', 'w')
        logger.debug("Writing helm repo index file...")
        yaml.dump(helm_index.model_dump(), yaml_file)
        logger.debug("DONE")
    except Exception as e:
        logger.error(e.with_traceback(None))

def _setup_osm_helm_repo():
    # Checking that the repo is not aready existing in OSM. Getting the repos and filter it with the name
    repo = next((item for item in nbiUtil.get_k8s_repos() if item['name'] == HELM_REPO_NAME), None)
    if repo is not None:
        logger.info('Deleting previous helm repository')
        nbiUtil.delete_k8s_repo(HELM_REPO_NAME)

    # Adding Helm repository to OSM
    # The repo name must not contain underscores _
    repo = nbiUtil.add_k8s_repo(HELM_REPO_NAME, f"http://{nfvcl_config.nfvcl.ip}:{nfvcl_config.nfvcl.port}{helm_url_prefix}")
    logger.info('Adding helm repo result: {}'.format(repo))

#helm_repo = HelmRepositoryManager()
#helm_repo.create_index()

