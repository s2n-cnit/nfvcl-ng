import json
from typing import List

from fastapi import APIRouter, HTTPException, Body, status
from kubernetes.client import V1PodList, V1Namespace, ApiException, V1ServiceAccountList, V1ServiceAccount, \
    V1ClusterRoleList, V1NamespaceList, V1RoleBinding, V1Secret, V1SecretList, V1ResourceQuota, V1ClusterRoleBinding, \
    V1Node, V1Deployment, V1DeploymentList, V1NodeList
from verboselogs import VerboseLogger

from nfvcl.main import topology_lock
from nfvcl.models.k8s.blueprint_k8s_model import TopologyK8sModel
from nfvcl.models.k8s.common_k8s_model import Labels
from nfvcl.models.k8s.plugin_k8s_model import K8sPluginsToInstall, K8sOperationType, K8sPluginName
from nfvcl.models.k8s.topology_k8s_model import K8sModelManagement, K8sQuota
from nfvcl.models.response_model import OssCompliantResponse, OssStatus
from nfvcl.rest_endpoints.rest_callback import RestAnswer202
from nfvcl.topology.topology import Topology
from nfvcl.utils.k8s import get_k8s_config_from_file_content, get_k8s_cidr_info, get_pods_for_k8s_namespace, k8s_create_namespace
from nfvcl.utils.k8s.helm_plugin_manager import HelmPluginManager
from nfvcl.utils.k8s.kube_api_utils import get_service_accounts, k8s_get_roles, get_k8s_namespaces, \
    k8s_admin_role_to_sa, \
    k8s_create_secret_for_user, k8s_create_service_account, k8s_get_secrets, k8s_cert_sign_req, \
    k8s_admin_role_over_namespace, \
    k8s_delete_namespace, k8s_add_quota_to_namespace, k8s_cluster_admin, k8s_add_label_to_k8s_node, k8s_get_nodes, \
    k8s_add_label_to_k8s_deployment, k8s_scale_k8s_deployment, k8s_get_deployments
from nfvcl.utils.log import create_logger
from nfvcl.utils.redis_utils.event_types import K8sEventType
from nfvcl.utils.redis_utils.redis_manager import get_redis_instance, trigger_redis_event
from nfvcl.utils.redis_utils.topic_list import K8S_MANAGEMENT_TOPIC

k8s_router = APIRouter(
    prefix="/k8s",
    tags=["Kubernetes cluster management"],
    responses={404: {"description": "Not found"}},
)
logger: VerboseLogger = create_logger('K8s Management REST endpoint')
redis_cli = get_redis_instance()


def get_k8s_cluster_by_id(cluster_id: str) -> TopologyK8sModel:
    """
    Get the k8s cluster from the topology. This method could be duplicated but in this case handle HTTP exceptions
    that give API user an idea of what is going wrong.

    Args:

        cluster_id: the cluster ID that identify a k8s cluster in the topology.

    Returns:

        The matching k8s cluster or Throw HTTPException if NOT found.
    """
    topology = Topology.from_db(topology_lock)
    k8s_clusters: List[TopologyK8sModel] = topology.get_k8s_clusters()
    match = next((x for x in k8s_clusters if x.name == cluster_id), None)

    if match:
        return match
    else:
        logger.error("K8s cluster {} not found".format(cluster_id))
        raise HTTPException(status_code=404, detail="K8s cluster {} not found".format(cluster_id))


def get_k8s_cluster_by_area(area_id: int) -> TopologyK8sModel:
    # TODO move in topology.py
    """
    Get the k8s cluster from the topology. This method could be duplicated but in this case handle HTTP exceptions
    that give API user an idea of what is going wrong.

    Args:

        area_id: the area id in of the cluster to get.

    Returns:

        The matching k8s cluster or Throw HTTPException if NOT found.
    """
    topology = Topology.from_db(topology_lock)
    k8s_clusters: List[TopologyK8sModel] = topology.get_k8s_clusters()
    match = next((x for x in k8s_clusters if area_id in x.areas), None)

    if match:
        return match
    else:
        error_msg = f"K8s cluster not found in area {area_id}"
        logger.error(error_msg)
        raise HTTPException(status_code=404, detail=error_msg)


@k8s_router.get("/{cluster_id}/plugins", response_model=List[K8sPluginName], summary="", description="")
async def get_k8s_installed_plugins(cluster_id: str):
    """
    Return installed plugins on a cluster

    Args:

        cluster_id: [str] the cluster id

    Returns:

        A list of installed plugins
    """
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    helm_plugin_manager = HelmPluginManager(cluster.credentials, "K8S REST UTILS")
    return helm_plugin_manager.get_installed_plugins()


@k8s_router.put("/{cluster_id}/plugins", response_model=RestAnswer202, status_code=status.HTTP_202_ACCEPTED)
async def install_k8s_plugin(cluster_id: str, message: K8sPluginsToInstall):
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
    # Return 404 error if the cluster does not exist
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)

    request = K8sModelManagement(k8s_ops=K8sOperationType.INSTALL_PLUGIN, cluster_id=cluster.name, data=json.dumps(message.model_dump()))

    trigger_redis_event(topic=K8S_MANAGEMENT_TOPIC, event_type=K8sEventType.PLUGIN_INSTALLED, data=request.model_dump())

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
    # Return 404 error if the cluster does not exist
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)

    request = K8sModelManagement(k8s_ops=K8sOperationType.APPLY_YAML, cluster_id=cluster_id, data=body.decode('utf-8'))

    trigger_redis_event(topic=K8S_MANAGEMENT_TOPIC, event_type=K8sEventType.DEFINITION_APPLIED, data=request.model_dump())

    return RestAnswer202(id='K8s management')


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
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Try to install plugins to cluster
        cidr_info = get_k8s_cidr_info(k8s_config)

    except ValueError as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return {"cidr": cidr_info}


@k8s_router.get("/{cluster_id}/pods", response_model=dict)
async def get_k8s_pods(cluster_id: str, namespace: str = ""):
    """
    Return pods from the desired cluster, filtered by namespace

    Args:

        cluster_id: the k8s cluster ID from which the pods are obtained

        namespace: the namespace of pods to be retrieved if empty pods are retrieved for all namespaces

    Returns:

        a V1PodList list with pod belonging to the specified namespace
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Try to install plugins to cluster
        pod_list: V1PodList = get_pods_for_k8s_namespace(kube_client_config=k8s_config, namespace=namespace)

    except ValueError as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return pod_list.to_dict()


@k8s_router.put("/{cluster_id}/namespace/{name}", response_model=OssCompliantResponse)
async def create_k8s_namespace(cluster_id: str, name: str = "", labels: dict = Body(...)):
    """
    Create a namespace on the target k8s cluster.

    Args:

        cluster_id: the k8s cluster ID on witch the namespace is created

        name: the name to be given at the new namespace

        labels: the labels to be applied at the namespace
                {
                    "label1": "ciao",
                    "label2": "test"
                }
                or
                {
                    "pod-security.kubernetes.io/enforce": "privileged"
                }

    Returns:
        the created namespace
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Try to install plugins to cluster
        created_namespace: V1Namespace = k8s_create_namespace(k8s_config, namespace_name=name, labels=labels)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        resp = OssCompliantResponse(status=OssStatus.failed, detail=str(val_err), result={})
        return resp

    resp = OssCompliantResponse(status=OssStatus.ready, detail="Namespace created", result=created_namespace.to_dict())
    return resp

@k8s_router.delete("/{cluster_id}/namespace/{name}", response_model=dict)
async def delete_k8s_namespace(cluster_id: str, name: str = ""):
    """
    Delete a namespace in the target k8s cluster.

    Args:

        cluster_id: the k8s cluster ID on witch the namespace is deleted

        name: the name of the namespace to be deleted

    Returns:
        the created namespace
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Try to install plugins to cluster
        created_namespace: V1Namespace = k8s_delete_namespace(k8s_config, namespace_name=name)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        resp = OssCompliantResponse(status=OssStatus.failed, detail=val_err, result={})
        return resp

    resp = OssCompliantResponse(status=OssStatus.ready, detail="Namespace deleted", result=created_namespace.to_dict())
    return resp


@k8s_router.get("/{cluster_id}/sa", response_model=dict)
async def get_k8s_service_account(cluster_id: str, username: str = "", namespace: str = ""):
    """
    Returns a list of service accounts

    Args:
        cluster_id: The cluster in which the function looks for users

        username: the username to filter the user list

        namespace: the namespace where users are searched

    Returns:
        A user list (V1ServiceAccountList)
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Retrieving service account list filtered by username and namespace
        user_accounts: V1ServiceAccountList = get_service_accounts(kube_client_config=k8s_config, username=username,
                                                                   namespace=namespace)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return user_accounts.to_dict()


@k8s_router.get("/{cluster_id}/roles", response_model=dict)
async def get_k8s_roles(cluster_id: str, rolename: str = "", namespace: str = ""):
    """
    Returns a list of roles

    Args:
        cluster_id: The cluster in which the function looks for roles

        rolename: the role name to use when filtering the role list

        namespace: the namespace where roles are searched

    Returns:
        A role list (V1ClusterRoleList)
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Retrieving service account list filtered by username and namespace
        role_list: V1ClusterRoleList = k8s_get_roles(kube_client_config=k8s_config, rolename=rolename,
                                                     namespace=namespace)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return role_list.to_dict()


@k8s_router.get("/{cluster_id}/namespaces", response_model=dict)
async def get_k8s_namespace_list(cluster_id: str, namespace: str = ""):
    """
    Returns a list of namespaces

    Args:
        cluster_id: The cluster in which the function looks for namespaces

        namespace: the name to use as filter

    Returns:
        A namespace list (V1NamespaceList)
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        namespace_list: V1NamespaceList = get_k8s_namespaces(kube_client_config=k8s_config, namespace=namespace)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return namespace_list.to_dict()


@k8s_router.post("/{cluster_id}/roles/admin/sa/{namespace}/{s_account}", response_model=dict)
async def give_admin_rights_to_sa(cluster_id: str, namespace: str, s_account: str, role_binding_name: str):
    """
    Give admin rights to an EXISTING service account (SA) in a namespace.

    Args:
        cluster_id: The target k8s cluster id

        namespace: The namespace on witch the admin rights are given to the target user.

        s_account: The existing service account that will become administrator

        role_binding_name: The name that will be given to the RoleBinding

    Returns:
        The created role binding (V1RoleBinding)
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Retrieving service account list filtered by username and namespace
        role_bind_res: V1RoleBinding = k8s_admin_role_to_sa(kube_client_config=k8s_config, namespace=namespace,
                                                            username=s_account, role_binding_name=role_binding_name)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return role_bind_res.to_dict()


@k8s_router.post("/{cluster_id}/roles/admin/{namespace}/{user}", response_model=dict)
async def give_admin_rights_to_user_namespaced(cluster_id: str, namespace: str, user: str, role_binding_name: str):
    """
    Give admin rights to a user (not necessarily existing) in a namespace. This call should be used, after a certificate
    signing request (CSR) has been issued and approved, for a user, to make him administrator (Note that this
    user won't exist in any namespace).

    Args:
        cluster_id: The target k8s cluster id

        namespace: The namespace on witch the admin rights are given to the target user.

        user: The user that will become administrator for the target namespace

        role_binding_name: The name that will be given to the RoleBinding

    Returns:
        The created role binding (V1RoleBinding)
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Retrieving service account list filtered by username and namespace
        role_bind_res: V1RoleBinding = k8s_admin_role_over_namespace(kube_client_config=k8s_config, namespace=namespace,
                                                                     username=user, role_binding_name=role_binding_name)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return role_bind_res.to_dict()


@k8s_router.post("/{cluster_id}/roles/cluster-admin/{user}", response_model=dict, summary="Give cluster admin rights to a user")
async def give_cluster_admin_rights(cluster_id: str, user: str, cluster_role_binding_name: str):
    """
    Give cluster admin rights to a user. This call should be used, after a certificate
    signing request (CSR) has been issued and approved, for a user, to make him administrator of the cluster

    Args:
        cluster_id: The target k8s cluster id

        user: The user that will become administrator for the cluster

        cluster_role_binding_name: The name that will be given to the ClusterRoleBinding

    Returns:
        The created role binding (V1RoleBinding)
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        role_bind_res: V1ClusterRoleBinding = k8s_cluster_admin(kube_client_config=k8s_config, username=user, role_binding_name=cluster_role_binding_name)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return role_bind_res.to_dict()


@k8s_router.put("/{cluster_id}/sa/{namespace}/{user}", response_model=dict)
async def create_service_account(cluster_id: str, namespace: str, user: str):
    """
    Create a service account for a namespace

    Args:
        cluster_id: The target cluster id

        namespace: The namespace in witch the user is created

        user: The name to be given at the user

    Returns:
        The created user (V1ServiceAccount)
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Creating service account
        user_creation_res: V1ServiceAccount = k8s_create_service_account(kube_client_config=k8s_config, namespace=namespace,
                                                                         username=user)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return user_creation_res.to_dict()


@k8s_router.post("/{cluster_id}/secret/{namespace}/{user}", response_model=dict)
async def create_secret_for_sa(cluster_id: str, namespace: str, user: str, secret_name: str):
    """
    Create secret for the target service account in a namespace

    Args:
        cluster_id: The cluster on witch the secret is created

        namespace: the mandatory namespace in witch the service account is created

        user: the mandatory name to be bounded at the service account

        secret_name: the mandatory name to be given at the created secret.

    Returns:
        The created secret (V1Secret)
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Retrieving service account list filtered by username and namespace
        created_secret: V1Secret = k8s_create_secret_for_user(kube_client_config=k8s_config,
                                                              namespace=namespace, username=user,
                                                              secret_name=secret_name)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return created_secret.to_dict()


@k8s_router.get("/{cluster_id}/secrets", response_model=dict)
async def get_secrets(cluster_id: str, namespace: str = "", secret_name: str = "", owner: str = ""):
    """
    Return a list of secrets for all namespaces. It is possible to filter retrieved secrets with optional parameters.

    Args:
        cluster_id: The mandatory target cluster

        namespace: used to filter secrets by namespace

        secret_name: used to filter secrets by their name

        owner: used to filter secrets by their owner

    Returns:
        The filtered list of secrets
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        auth_response: V1SecretList = k8s_get_secrets(kube_client_config=k8s_config,
                                                      namespace=namespace, secret_name=secret_name, owner=owner)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return auth_response.to_dict()


@k8s_router.post("/{cluster_id}/sa/{namespace}/{username}", response_model=dict, summary="Create SA with admin right on the namespace")
async def create_admin_sa_for_namespace(cluster_id: str, namespace: str, username: str):
    """
    Create a Service Account in the target namespace, with admin rights.
    1 - Create the user
    2 - Role bind the admin role to the user on the target namespace
    3 - Create a secret for the user
    4 - Return created resources

    Args:
        cluster_id: The target k8s cluster.

        namespace: The namespace in which the user is created

        username: The name of the user

    Returns:
        a dictionary containing the created resources:
        {"service_account": sa.to_dict(),
        "binding_role": role.to_dict(),
        "secret": detailed_secret.to_dict()}

    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        # Creating SA
        sa = k8s_create_service_account(kube_client_config=k8s_config, namespace=namespace, username=username)
        # Creating role binding to be admin
        binding_name = "rolebinding_admin_" + username
        role = k8s_admin_role_to_sa(kube_client_config=k8s_config, namespace=namespace, username=username, role_binding_name=binding_name)
        # Create secret
        secret_name = username + "-secret"
        secret = k8s_create_secret_for_user(kube_client_config=k8s_config, namespace=namespace, username=username, secret_name=secret_name)
        # Returning secret WITH token included
        detailed_secret = k8s_get_secrets(kube_client_config=k8s_config, namespace=namespace, secret_name=secret.metadata.name)

        result = {"service_account": sa.to_dict(),
                  "binding_role": role.to_dict(),
                  "secret": detailed_secret.to_dict()}

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return result


@k8s_router.post("/{cluster_id}/user/{username}", response_model=dict, summary="Create (the user) and retrieve info for a new kubectl user")
async def create_k8s_kubectl_user(cluster_id: str, username: str, expire_seconds: int = 31536000):
    """
    Create user credentials for kubectl. This function will generate a private key and a certificate to use for talking with the
    cluster through kubectl or equivalent software.

    Args:
        cluster_id: The cluster on which the user is created

        username: The name to be given at the user

        expire_seconds: The validity of the user in seconds (default 1 Year = 365 days = 31536000 seconds)

    Returns:
        a dictionary containing: server certificate, user private key and user certificate in BASE 64 format to be used in kubectl after being
        converted from base64.
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        auth_response: dict = k8s_cert_sign_req(kube_client_config=k8s_config, username=username,
                                                expiration_sec=expire_seconds)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(val_err))

    return auth_response


@k8s_router.post("/{cluster_id}/quota/{namespace}/{quota_name}", response_model=OssCompliantResponse)
async def apply_resource_quota_namespace(cluster_id: str, namespace: str, quota_name: str, quota: K8sQuota):
    """
    Add a quota reservation (for resources) to the namespace.
    Args:
        cluster_id: The cluster on witch the quota is created

        namespace: The namespace target of the quota reservation

        quota_name: The name of the reservation

        quota: The quantities to be reserved

    Returns:
        The created quota.
    """

    # Get k8s cluster and k8s config for client
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)

    try:
        quota_resp: V1ResourceQuota = k8s_add_quota_to_namespace(kube_client_config=k8s_config, namespace_name=namespace,
                                                                 quota_name=quota_name, quota=quota)

    except (ValueError, ApiException) as val_err:
        logger.error(val_err)
        resp = OssCompliantResponse(status=OssStatus.failed, detail=val_err.body, result={})
        return resp

    resp = OssCompliantResponse(status=OssStatus.ready, detail="Quota created", result=quota_resp.to_dict())
    return resp


@k8s_router.get("/{cluster_id}/nodes/", response_model=dict)
async def get_nodes(cluster_id: str, detailed: bool = False):
    """
    Returns a list of nodes belonging to a k8s cluster

    Args:

        cluster_id:  The K8s cluster (from the topology) on witch nodes resides

        detailed: If true, a list with only names is retrieved, otherwise a V1PodList in dict form is retrieved.

    Returns:
        If detailed a list with only names is retrieved, otherwise a V1PodList in dict form is retrieved.
    """
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)
    if detailed:
        node_list: V1NodeList = k8s_get_nodes(k8s_config, detailed=detailed)
        to_return = node_list.to_dict()
    else:
        name_list = k8s_get_nodes(k8s_config, detailed=detailed)
        to_return = {"nodes": name_list}
    return to_return


@k8s_router.post("/{cluster_id}/node/{node_name}/", response_model=dict)
async def add_label_to_k8s_node(cluster_id: str, node_name: str, labels: Labels):
    """
    Add labels to a k8s node

    Args:

        cluster_id: The K8s cluster (from the topology) on witch the node resides

        node_name: the name of the node on witch labels is applied

        labels: The labels to be applied

    Returns:
        The updated node V1Node in dict form
    """
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)
    node: V1Node = k8s_add_label_to_k8s_node(k8s_config, node_name=node_name, labels=labels)
    return node.to_dict()


@k8s_router.get("/{cluster_id}/deployments/", response_model=dict)
async def get_deployment(cluster_id: str, namespace: str, detailed: bool = False):
    """
    Returns a list of deployments belonging to a k8s cluster

    Args:

        cluster_id: The K8s cluster (from the topology) on witch deployments resides

        namespace: The namespace in which the deployment resides

        detailed: If true, a list with only names is retrieved, otherwise a V1DeploymentList in dict form is retrieved.

    Returns:
        If detailed a list with only names is retrieved, otherwise a V1PodList in dict form is retrieved.
    """
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)
    if detailed:
        deployment_list: V1DeploymentList = k8s_get_deployments(k8s_config, namespace=namespace, detailed=detailed)
        to_return = deployment_list.to_dict()
    else:
        name_list = k8s_get_deployments(k8s_config, namespace=namespace, detailed=detailed)
        to_return = {"deployments": name_list}
    return to_return


@k8s_router.post("/{cluster_id}/deployment/label", response_model=dict)
async def add_label_to_k8s_deployment(cluster_id: str, namespace: str, deployment_name: str, labels: Labels):
    """
    Add labels to a k8s node

    Args:
        cluster_id: The K8s cluster (from the topology) on witch the deployment resides
        namespace: The namespace in which the deployment resides
        deployment_name: the name of the deployment on witch labels is applied
        labels: The labels to be applied

    Returns:
        The updated node V1Deployment in dict form
    """
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)
    deployment: V1Deployment = k8s_add_label_to_k8s_deployment(k8s_config, namespace=namespace, deployment_name=deployment_name, labels=labels)
    return deployment.to_dict()


@k8s_router.post("/{cluster_id}/deployment/scale", response_model=dict)
async def scale_k8s_deployment(cluster_id: str, namespace: str, deployment_name: str, replica_number: int):
    """
    Scale a deployment in the cluster

    Args:
        cluster_id: The K8s cluster (from the topology) on witch the deployment resides
        namespace: The namespace in which the deployment resides
        deployment_name: the name of the deployment that will be scaled
        replica_number: The desired number of pods (scaling)

    Returns:
        The updated node V1Deployment in dict form
    """
    cluster: TopologyK8sModel = get_k8s_cluster_by_id(cluster_id)
    k8s_config = get_k8s_config_from_file_content(cluster.credentials)
    deployment: V1Deployment = k8s_scale_k8s_deployment(k8s_config, namespace=namespace, deployment_name=deployment_name, replica_num=replica_number)
    return deployment.to_dict()
