import json
from logging import Logger
from typing import List
from fastapi import APIRouter, HTTPException, Body, status
from models.k8s import K8sModel
from main import *
from models.k8s.k8s_models import K8sPluginName, K8sOperationType, K8sModelManagement
from rest_endpoints.rest_callback import RestAnswer202
from topology import Topology
from utils.k8s import get_k8s_config_from_file_content, check_installed_plugins, get_k8s_cidr
from utils.redis.redis_manager import get_redis_instance

k8s_router = APIRouter(
    prefix="/k8s",
    tags=["Kubernetes cluster management"],
    responses={404: {"description": "Not found"}},
)
logger: Logger = create_logger('K8s Management REST endpoint')
redis_cli = get_redis_instance()


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


@k8s_router.put("/{cluster_id}/plugins", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def install_plugin_to_k8s(cluster_id: str, message: List[K8sPluginName]):
    """
    Install required plugins to the target k8s clusters. The operation is made asynchronously and output can be observed
    on NFVCL log at redis. Otherwise, this method will be blocking.

    Args:

        cluster_id: String. The cluster ID of the k8s belonging to the topology in which the yaml will be applied.

        message: the list of K8s plugins to install.

    Returns:

        The k8s response in that confirm the submission of the requested operation. You can observe process output
        subscribing to NFVCL log at the redis instance.
    """

    request = K8sModelManagement(k8s_ops=K8sOperationType.INSTALL_PLUGIN, cluster_id=cluster_id,
                                 data=json.dumps(message))
    redis_cli.publish("K8S_MAN", request.json())

    return RestAnswer202(id='K8s management')


@k8s_router.put("/{cluster_id}/yaml", response_model=RestAnswer202)
async def apply_to_k8s(cluster_id: str, body=Body(...)):
    """
    Apply a yaml content to the target k8s cluster. The specified resources in the yaml file MUST NOT exist. The
    operation is done in background, result can be observed from NFVCL log.

    Args:

        cluster_id: The cluster ID of the k8s belonging to the topology in which the yaml will be applied.

        body: The yaml content to apply at the cluster

    """
    request = K8sModelManagement(k8s_ops=K8sOperationType.APPLY_YAML, cluster_id=cluster_id,
                                 data=body.decode('utf-8'))
    redis_cli.publish("K8S_MAN", request.json())

    return RestAnswer202(id='K8s management')


@k8s_router.delete("/{cluster_id}/plugins", response_model=RestAnswer202)
async def uninstall_plugin_from_k8s(cluster_id: str, message: List[K8sPluginName]):
    """
    # TODO
    Still not implemented
    """
    return RestAnswer202(id='K8s management', description="This operation is still not implemented",
                         status="NOT IMPLEMENTED")


@k8s_router.get("/{cluster_id}/cidr", response_model=dict)
async def get_k8s_cidr(cluster_id: str):
    """
    Return the pod network CIDR.

    Args:

        cluster_id: the k8s cluster ID from witch the CIDR is obtained

    Returns:

        a dict {"cidr": "x.y.z.k/z"} containing the cidr of the pod network.
    """

    # Get k8s cluster and k8s config for client
    cluster: K8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Try to install plugins to cluster
        cidr_info = get_k8s_cidr(k8s_config)

    except ValueError as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return {"cidr": cidr_info}
