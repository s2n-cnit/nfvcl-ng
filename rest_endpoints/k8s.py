from logging import Logger
from typing import List
from fastapi import APIRouter, HTTPException, Body, status
from kubernetes.utils import FailToCreateError
from models.k8s import K8sModel
from main import *
from models.k8s.k8s_models import K8sPluginName
from topology import Topology
from utils.k8s import get_k8s_config_from_file_content, apply_def_to_cluster, check_installed_plugins, \
    install_plugins_to_cluster
from models.k8s import K8sDaemon

k8s_router = APIRouter(
    prefix="/k8s",
    tags=["Kubernetes cluster management"],
    responses={404: {"description": "Not found"}},
)
logger: Logger = create_logger('K8s Management REST endpoint')


def get_k8s_cluster_by_id(cluster_id: str) -> K8sModel:
    """
    Get the k8s cluster from the topology. This method could be duplicated but in this case handle HTTP exceptions
    that give API user an idea of what is going wrong.

    Args:

        cluster_id: the cluster ID that identify a k8s cluster in the topology.

    Returns:

        The matching k8s cluster or Throw HTTPException if NOT found.
    """
    try:
        topology = Topology.from_db(db, nbiUtil, topology_lock)
        k8s_clusters: List[K8sModel] = topology.get_k8scluster_model()
        match = next((x for x in k8s_clusters if x.name == cluster_id), None)

        if match:
            return match
        else:
            logger.error("K8s cluster {} not found".format(cluster_id))
            raise HTTPException(status_code=404, detail="K8s cluster {} not found".format(cluster_id))
    except Exception as err:
        logger.error(err)
        raise HTTPException(status_code=400, detail="Failed getting k8s cluster {}".format(cluster_id))


@k8s_router.put("/{cluster_id}", response_model=List[dict])
async def apply_to_k8s(cluster_id: str, body=Body(...)):
    """
    Apply a yaml content to the target k8s cluster. The specified resources in the yaml file MUST NOT exist.

    Args:

        cluster_id: The cluster ID of the k8s belonging to the topology in which the yaml will be applied.

        body: The yaml content to apply at the cluster

    Returns:

        List[dict]: the list of created resources returned from the k8s cluster.
    """
    cluster: K8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    body_string = body.decode("utf8")

    yaml_request = yaml.safe_load(body_string)

    try:
        result = apply_def_to_cluster(kube_client_config=k8s_config, dict_to_be_applied=yaml_request)
    except FailToCreateError as err:
        logger.error(err)
        if err.args[0][0].status == status.HTTP_409_CONFLICT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="The resource already exist")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Error during resource creation")
    # Element in position zero because apply_def_to_cluster is working on dictionary, please look at the source
    # code of apply_def_to_cluster
    list_to_ret: List[dict] = []
    for element in result[0]:
        list_to_ret.append(element.to_dict())
    return list_to_ret


@k8s_router.get("/{cluster_id}/plugins", response_model=List[K8sPluginName], summary="", description="")
async def get_installed_plugins(cluster_id: str):
    """
    Return installed plugins on a cluster

    Args:

        cluster_id: [str] the cluster id

    Returns:

        A list of installed plugins
    """

    cluster: K8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    installed_plugins = check_installed_plugins(kube_client_config=k8s_config)

    return installed_plugins


@k8s_router.put("/{cluster_id}/plugins", response_model=dict)
async def install_plugins(cluster_id: str, message: List[K8sPluginName], detailed: bool = False):
    """
    Install required plugins to the target k8s clusters.

    Args:

        cluster_id: String. The cluster ID of the k8s belonging to the topology in which the yaml will be applied.
        message: the list of K8sDaemon to install (plugins)

        detailed: if the response is detailed, its content correspond to k8s response. Othewise it is just a list of
        installed plugins.

    Returns:

        The k8s response if detailed, a list of installed plugins otherwise.
    """

    # Get k8s cluster and k8s config for client
    cluster: K8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Try to install plugins to cluster
        installation_result: dict = install_plugins_to_cluster(kube_client_config=k8s_config,
                                                               plugins_to_install=message)
    except ValueError as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    # If detailed parse all the content from k8s otherwise just a list of installed plugins
    if detailed:
        # Transforming object inside into dictionaries from object
        for plugin_result in installation_result:
            for resource_type in installation_result[plugin_result]:
                for i in range(0, len(resource_type)):
                    resource_type[i] = resource_type[i].to_dict()

        return installation_result
    else:
        # Return only the name of installed plugins
        to_return = []
        for plugin_result in installation_result:
            to_return.append(plugin_result)

        return {"installed_plugins": to_return}