import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import kubernetes
import kubernetes.client
import kubernetes.utils
import yaml
from kubernetes.client import V1ServiceAccountList, ApiException, V1ServiceAccount, V1ClusterRoleList, V1ClusterRole, \
    V1Namespace, V1NamespaceList, V1ObjectMeta, V1RoleBinding, V1Subject, V1RoleRef, V1Secret, V1SecretList, \
    V1CertificateSigningRequest, V1CertificateSigningRequestSpec, V1CertificateSigningRequestStatus, \
    V1CertificateSigningRequestCondition, V1Role, V1PolicyRule, V1Pod, V1Container, V1ResourceQuota, \
    V1ResourceQuotaSpec, V1ClusterRoleBinding, V1Node, V1NodeList, V1DeploymentList, V1Deployment, V1DeploymentSpec, V1StorageClassList, V1PodList, V1DaemonSetList, V1ServiceList, V1ConfigMap, VersionInfo, V1StorageClass
from verboselogs import VerboseLogger

from nfvcl_core_models.k8s_management_models import Labels

from nfvcl_core_models.topology_k8s_model import K8sQuota, K8sVersion
from nfvcl_core.utils.k8s.k8s_client_extension import create_from_yaml_custom
from nfvcl_core.utils.log import create_logger
from nfvcl_core.utils.util import generate_rsa_key, generate_cert_sign_req, convert_to_base64

logger: VerboseLogger = create_logger("K8s API utils")

TIMEOUT_SECONDS = 10


def get_service_accounts(kube_client_config: kubernetes.client.Configuration, namespace: str = None,
                         username: str = "") -> V1ServiceAccountList:
    """
    Retrieve all users of a namespace. If a namespace is not specified, it will work on
    all namespaces.
    There is the possibility to filter on username

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: the optional namespace. If None users are retrieved from all namespaces.
        username: the optional username to filter users.

    Returns:
        an object V1ServiceAccountList containing a list of V1AccountList
    """
    field_selector = ''
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the apps API
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        try:
            if username != "":
                field_selector = 'metadata.name=' + username
            if namespace:
                if not k8s_check_namespace_exist(kube_client_config, namespace):
                    raise ValueError("Namespace ->{}<- does not exist.")
                service_accounts: V1ServiceAccountList = api_instance_core.list_namespaced_service_account(
                    namespace=namespace, field_selector=field_selector, timeout_seconds=TIMEOUT_SECONDS)
            else:
                service_accounts: V1ServiceAccountList = api_instance_core.list_service_account_for_all_namespaces(
                    field_selector=field_selector, timeout_seconds=TIMEOUT_SECONDS)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api in get_service_accounts: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return service_accounts


def k8s_check_sa_exist(kube_client_config: kubernetes.client.Configuration, username: str,
                       namespace: str = None) -> V1ServiceAccount:
    """
    Check that a SA exist. Raise ValueError if not found or if found multiple instance.
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        username: the mandatory username to filter users.
        namespace: the optional namespace. If None users are retrieved from all namespaces.
    Returns:
        The target user if found.

    Raises:
        ValueError if no user is found or if multiple users are found
    """
    account_list: V1ServiceAccountList = get_service_accounts(kube_client_config, namespace, username)
    if len(account_list.items) <= 0:
        if namespace:
            raise ValueError("User ->{}<- not found in namespace {}".format(username, namespace))
        else:
            raise ValueError("User ->{}<- not found".format(username))
    elif len(account_list.items) == 1:
        return account_list.items[0]
    else:
        if namespace:
            raise ValueError("Not unique match for user ->{}<- in namespace {}".format(username, namespace))
        else:
            raise ValueError("Not unique match for user ->{}<-".format(username))


def k8s_get_roles(kube_client_config: kubernetes.client.Configuration, namespace: str = None,
                  rolename: str = None) -> V1ClusterRoleList:
    """
    Retrieve all roles of a namespace. If a namespace is not specified, it will work on
    all namespaces.
    There is the possibility to filter roles on role name.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: the optional namespace. If None roles are retrieved from all namespaces.
        rolename: the optional role name to filter roles.

    Returns:
        an object V1ServiceAccountList containing a list of V1AccountList
    """
    field_selector = ''
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the RBAC API
        api_instance_rbac = kubernetes.client.RbacAuthorizationV1Api(api_client)
        try:
            if rolename != "":
                field_selector = 'metadata.name=' + rolename
            if namespace:
                if not k8s_check_namespace_exist(kube_client_config, namespace):
                    raise ValueError("Namespace ->{}<- does not exist.")
                role_list: V1ClusterRoleList = api_instance_rbac.list_namespaced_role(
                    namespace=namespace, field_selector=field_selector, timeout_seconds=TIMEOUT_SECONDS)
            else:
                role_list: V1ClusterRoleList = api_instance_rbac.list_role_for_all_namespaces(
                    field_selector=field_selector, timeout_seconds=TIMEOUT_SECONDS)
        except ApiException as error:
            logger.error("Exception when calling RbacAuthorizationV1Api in get_k8s_role: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return role_list


def k8s_check_role_exist(kube_client_config: kubernetes.client.Configuration, namespace: str = None,
                         rolename: str = None) -> V1ClusterRole:
    """
    Check that a role exist. Raise ValueError if not found or if found multiple instance.
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        rolename: the mandatory name for the role to filter roles.
        namespace: the optional namespace. If None roles are retrieved from all namespaces.
    Returns:
        The target role if found.

    Raises:
        ValueError if no role is found or if multiple roles are found
    """
    role_list: V1ClusterRoleList = k8s_get_roles(kube_client_config, namespace, rolename)
    if len(role_list.items) <= 0:
        if namespace:
            raise ValueError("Role ->{}<- not found in namespace {}".format(rolename, namespace))
        else:
            raise ValueError("Role ->{}<- not found".format(rolename))
    elif len(role_list.items) == 1:
        return role_list.items[0]
    else:
        if namespace:
            raise ValueError("Not unique match for role ->{}<- in namespace {}".format(rolename, namespace))
        else:
            raise ValueError("Not unique match for role ->{}<-".format(rolename))


def get_k8s_namespaces(kube_client_config: kubernetes.client.Configuration, namespace: str = None) -> V1NamespaceList:
    """
    Retrieve all namespaces. If a namespace is specified it return that namespace.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: the optional namespace, could lead to empty list. If absent all namespaces are retrieved.

    Returns:
        an object V1NamespaceList containing a list of namespaces. Could be empty if specified namespace does not exist.

    Raises:
        ApiException if an error occurs during the API call.
    """
    field_selector = ''
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the CORE API
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        try:
            if namespace and namespace != '':
                field_selector = 'kubernetes.io/metadata.name=' + namespace
            namespace_list: V1NamespaceList = api_instance_core.list_namespace(label_selector=field_selector,
                                                                               timeout_seconds=TIMEOUT_SECONDS)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api in get_k8s_namespace: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return namespace_list


def k8s_check_namespace_exist(kube_client_config: kubernetes.client.Configuration, namespace: str) -> V1Namespace:
    """
    Check that a namespace exist. Raise ValueError if not found or if found multiple instance.
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: the mandatory name of namespace.
    Returns:
        The target namespace if found.

    Raises:
        ValueError if no role is found or if multiple roles are found
    """
    role_list: V1NamespaceList = get_k8s_namespaces(kube_client_config, namespace)
    if len(role_list.items) <= 0:
        raise ValueError("Namespace ->{}<- not found".format(namespace))
    elif len(role_list.items) == 1:
        return role_list.items[0]
    else:
        raise ValueError("Not unique match for namespace ->{}<-".format(namespace))


def k8s_create_service_account(kube_client_config: kubernetes.client.Configuration, namespace: str,
                               username: str) -> V1ServiceAccount:
    """
    Create a service account in a namespace

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: the mandatory namespace in witch the service account is created
        username: the name of the service account

    Returns:
        The created service account
    """
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the CORE API
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        try:
            metadata: V1ObjectMeta = V1ObjectMeta(name=username, namespace=namespace)
            sa: V1ServiceAccount = V1ServiceAccount(metadata=metadata)
            created_sa: V1ServiceAccount = api_instance_core.create_namespaced_service_account(namespace, body=sa)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api in k8s_create_service_account: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return created_sa


def k8s_create_admin_role(kube_client_config: kubernetes.client.Configuration, namespace: str) -> V1Role:
    """
    Warnings:
        CAN be called once per namespace!!
    """
    if not k8s_check_namespace_exist(kube_client_config, namespace):
        raise ValueError("Namespace ->{}<- does not exist.".format(namespace))
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the RBAC API
        api_instance_rbac = kubernetes.client.RbacAuthorizationV1Api(api_client)
        try:
            metadata: V1ObjectMeta = V1ObjectMeta(name="nfvclAdmin")
            # Admin role
            rules = [V1PolicyRule(api_groups=['*'], resources=['*'], verbs=['*'])]

            role = V1Role(rules=rules, metadata=metadata)
            role_res: V1Role = api_instance_rbac.create_namespaced_role(namespace=namespace, body=role)
        except ApiException as error:
            logger.error("Exception when calling RbacAuthorizationV1Api in k8s_create_admin_role: {}\n".format(error))
            raise error
        finally:
            api_client.close()
        return role_res


def k8s_admin_role_to_sa(kube_client_config: kubernetes.client.Configuration, namespace: str, username: str,
                         role_binding_name: str) -> V1RoleBinding:
    """
    Give to an EXISTING service account the admin role on a namespace.
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: the target namespace where the user reside
        username: the name of the service account that will become administrator of the namespace
        role_binding_name: the name that will be given to the rule.

    Returns:
        The created role binding to administrator.
    """
    if not k8s_check_namespace_exist(kube_client_config, namespace):
        raise ValueError("Namespace ->{}<- does not exist.".format(namespace))
    if not k8s_check_sa_exist(kube_client_config, username, namespace):
        # Not critical, can exist a role binding to a user(service account) that is not inside namespace
        logger.warning("User ->{}<- in {} namespace.".format(username, namespace))
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the RBAC API
        api_instance_rbac = kubernetes.client.RbacAuthorizationV1Api(api_client)
        try:
            metadata: V1ObjectMeta = V1ObjectMeta(name=role_binding_name)

            subjects = [V1Subject(kind='User', name=username)]
            role_ref = V1RoleRef(kind='Role', name='admin', api_group='rbac.authorization.k8s.io')

            role_bind = V1RoleBinding(subjects=subjects, role_ref=role_ref, metadata=metadata)
            role_bind_res: V1RoleBinding = api_instance_rbac.create_namespaced_role_binding(namespace=namespace,
                                                                                            body=role_bind)
        except ApiException as error:
            logger.error("Exception when calling RbacAuthorizationV1Api in k8s_admin_role_to_user: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return role_bind_res


def k8s_admin_role_over_namespace(kube_client_config: kubernetes.client.Configuration, namespace: str, username: str,
                                  role_binding_name: str) -> V1RoleBinding:
    """
    This function is specific to give admin rights on a user that is not present explicitly inside a k8s cluster.
    For example, when new certificates are created for k8s API, the user does not exist in namespaces, it is not a
    service account.
    Give to a user (could not exist in namespaces, for example through certificates) the admin role on a namespace.
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: the target namespace where the user reside
        username: the name of the user that will become administrator of the namespace. The uses
        role_binding_name: the name that will be given to the rule.

    Returns:
        The created role binding to administrator.
    """
    if not k8s_check_namespace_exist(kube_client_config, namespace):
        raise ValueError("Namespace ->{}<- does not exist.".format(namespace))
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the RBAC API
        api_instance_rbac = kubernetes.client.RbacAuthorizationV1Api(api_client)
        # Checking if admin role exist, otherwise create it
        try:
            k8s_check_role_exist(kube_client_config, namespace, rolename='nfvclAdmin')
        except ValueError as e:
            # Does not exist or multiple account found
            k8s_create_admin_role(kube_client_config, namespace)
        try:
            metadata: V1ObjectMeta = V1ObjectMeta(name=role_binding_name)

            subjects = [V1Subject(kind='User', name=username)]
            role_ref = V1RoleRef(kind='Role', name='nfvclAdmin', api_group='rbac.authorization.k8s.io')

            role_bind = V1RoleBinding(subjects=subjects, role_ref=role_ref, metadata=metadata)
            role_bind_res: V1RoleBinding = api_instance_rbac.create_namespaced_role_binding(namespace=namespace,
                                                                                            body=role_bind)
        except ApiException as error:
            logger.error("Exception when calling RbacAuthorizationV1Api in k8s_admin_role_to_user: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return role_bind_res


def k8s_cluster_admin(kube_client_config: kubernetes.client.Configuration, username: str, role_binding_name: str) -> V1ClusterRoleBinding:
    """
    This function is specific to give CLUSTER admin rights on a user.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.

        username: the name of the user that will become cluster administrator

        role_binding_name: the name that will be given to the cluister role binding.

    Returns:
        The created cluster role binding for administrator.
    """

    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the RBAC API
        api_instance_rbac = kubernetes.client.RbacAuthorizationV1Api(api_client)
        try:
            metadata: V1ObjectMeta = V1ObjectMeta(name=role_binding_name)

            subjects = [V1Subject(kind='User', name=username)]
            role_ref = V1RoleRef(kind='ClusterRole', name='cluster-admin', api_group='rbac.authorization.k8s.io')

            role_bind = V1ClusterRoleBinding(subjects=subjects, role_ref=role_ref, metadata=metadata)
            role_bind_res: V1ClusterRoleBinding = api_instance_rbac.create_cluster_role_binding(body=role_bind)
        except ApiException as error:
            logger.error("Exception when calling RbacAuthorizationV1Api in k8s_cluster_admin: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return role_bind_res


def k8s_create_secret_for_user(kube_client_config: kubernetes.client.Configuration, namespace: str, username: str,
                               secret_name: str) -> V1Secret:
    """
    Create a secret for a user.
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: The namespace where the user reside
        username: The user to which the secret is assigned
        secret_name: The name given at the secret

    Returns:
        The created secret
    """
    if not k8s_check_namespace_exist(kube_client_config, namespace):
        raise ValueError("Namespace ->{}<- does not exist.".format(namespace))
    service_account: V1ServiceAccount = k8s_check_sa_exist(kube_client_config, username, namespace)
    if not service_account:
        raise ValueError("User ->{}<- in {} namespace.".format(username, namespace))

    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the Core API
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        try:
            annotations = {'kubernetes.io/service-account.name': username}
            metadata: V1ObjectMeta = V1ObjectMeta(name=secret_name, annotations=annotations)

            auth_req = V1Secret(metadata=metadata, type="kubernetes.io/service-account-token")
            auth_resp: V1Secret = api_instance_core.create_namespaced_secret(namespace=namespace, body=auth_req)
        except ApiException as error:
            logger.error(
                "Exception when calling RbacAuthorizationV1Api in k8s_create_secret_for_user: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return auth_resp


def k8s_get_secrets(kube_client_config: kubernetes.client.Configuration, namespace: str = "", secret_name: str = "",
                    owner: str = "") -> V1SecretList:
    """
    Retrieve secrets from k8s cluster

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: optional to filter secrets on namespace
        secret_name: optional to filter secrets on their name
        owner: optional to filter secrets on the owner

    Returns:
        A filtered list of secrets
    """
    field_selector = ''
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the CORE API
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        try:
            if secret_name != "":
                field_selector = 'metadata.name=' + secret_name

            if namespace != "":
                if not k8s_check_namespace_exist(kube_client_config, namespace):
                    raise ValueError("Namespace ->{}<- does not exist.".format(namespace))
                secret_list: V1SecretList = api_instance_core.list_namespaced_secret(namespace=namespace,
                                                                                     field_selector=field_selector)
            else:
                secret_list: V1SecretList = api_instance_core.list_secret_for_all_namespaces(
                    field_selector=field_selector)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api in k8s_get_secrets: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        to_return_list = []
        if owner != "":
            secret: V1Secret
            for secret in secret_list.items:
                annotations: dict = secret.metadata.annotations
                if annotations is not None:
                    if 'kubernetes.io/service-account.name' in annotations.keys():
                        if annotations['kubernetes.io/service-account.name'] == owner:
                            to_return_list.append(secret)
            secret_list.items = to_return_list

        return secret_list


def k8s_cert_sign_req(kube_client_config: kubernetes.client.Configuration, username: str,
                      expiration_sec: int = 63072000) -> dict:
    """
    TODO comment
    Args:
        kube_client_config:
        username:
        expiration_sec:

    Returns:

    """
    key, private_key = generate_rsa_key()
    # IMPORTANT the username inside cert will be the username arriving at API server!
    # When giving permissions with binding roles, this is the subject!
    cert_sign_req = generate_cert_sign_req(username, key)
    cert_sign_req_base64 = convert_to_base64(cert_sign_req)

    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the CORE API
        api_instance_core = kubernetes.client.CertificatesV1Api(api_client)
        api_instance_secrets = kubernetes.client.CoreV1Api(api_client)
        try:
            # CSR
            usages = ["client auth"]
            csr_spec = V1CertificateSigningRequestSpec(request=cert_sign_req_base64,
                                                       signer_name='kubernetes.io/kube-apiserver-client',
                                                       expiration_seconds=expiration_sec, usages=usages)

            metadata = V1ObjectMeta(name=username)
            v1csr = V1CertificateSigningRequest(spec=csr_spec, metadata=metadata)
            csr_result: V1CertificateSigningRequest = api_instance_core.create_certificate_signing_request(body=v1csr)

            condition = V1CertificateSigningRequestCondition(message="This CSR was approved by NFVCL",
                                                             reason="NFVCL Kubectl user",
                                                             status="True",
                                                             type="Approved")
            conditions = [condition]
            status = V1CertificateSigningRequestStatus(conditions=conditions)
            csr_result.status = status
            csr_approbation: V1CertificateSigningRequest = api_instance_core.patch_certificate_signing_request_approval(
                name=username, body=csr_result)
            # Need to sleep otherwise the cert is still not ready
            time.sleep(0.10)
            csr_result: V1CertificateSigningRequest = api_instance_core.read_certificate_signing_request(
                name=username)

            ############ GET cluster certificate ##########
            cm_list = api_instance_secrets.list_namespaced_config_map(namespace="default")
            ca_root = [item for item in cm_list.items if item.metadata.name == 'kube-root-ca.crt']
            if len(ca_root) <= 0:
                logger.error("No kube-root-ca.crt found in the cluster")

            ca_root_data = ca_root[0].data['ca.crt']
        except (ValueError, ApiException) as error:
            logger.error("Exception when calling CertificatesV1Api in k8s_cert_sign_req: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        # Making private key clean from PEM embedding and '\n'
        private_key_base64 = convert_to_base64(private_key)
        ca_root_data_b64 = convert_to_base64(str.encode(ca_root_data))

        to_return = {"cluster_cert": ca_root_data_b64,
                     "user_key_b64": private_key_base64,
                     "user_priv_cert_b64": csr_result.status.certificate,
                     "csr_approved": csr_result.to_dict()}

        return to_return

def k8s_create_namespace(kube_client_config: kubernetes.client.Configuration, namespace_name: str, labels: dict) -> V1Namespace:
    """
    Create a namespace in a k8s cluster.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace_name: The name of the namespace to be created
        labels: The labels to be assigned to the namespace

    Returns:
        The created namespace
    """
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the API class
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        metadata = V1ObjectMeta(name=namespace_name, labels=labels)
        namespace_body = V1Namespace(metadata=metadata)
        try:
            namespace = api_instance_core.create_namespace(body=namespace_body)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api>create_namespace: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return namespace



def k8s_delete_namespace(kube_client_config: kubernetes.client.Configuration, namespace_name: str) -> V1Namespace:
    """
    Delete a namespace in a k8s cluster.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace_name: The name of the namespace to be deleted

    Returns:
        The deleted namespace
    """
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the API class
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        try:
            namespace = api_instance_core.delete_namespace(namespace_name)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api>delete_namespace: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return namespace


def k8s_add_quota_to_namespace(kube_client_config: kubernetes.client.Configuration, namespace_name: str,
                               quota_name: str, quota: K8sQuota) -> V1ResourceQuota:
    """
    Add a quota (for resources) to the namespace
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace_name: The namespace on witch the quota is applied
        quota_name: The name of the quota reservation
        quota: The quantities to be reserved

    Returns:
        The created quota.
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_core = kubernetes.client.CoreV1Api(api_client)

        spec = quota.model_dump(by_alias=True)
        res_spec = V1ResourceQuotaSpec(hard=spec)
        metadata = V1ObjectMeta(name=quota_name)
        res_quota = V1ResourceQuota(metadata=metadata, spec=res_spec)

        try:
            created_quota = api_instance_core.create_namespaced_resource_quota(namespace=namespace_name, body=res_quota)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api>patch_namespaced_pod: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return created_quota


def k8s_add_container_to_namespaced_deployment(kube_client_config: kubernetes.client.Configuration, namespace_name: str, deployment_name: str, container: V1Container) -> V1Namespace:
    """
    Add a container to the deployment. Can be used to inject sidecars into Pods of a Deployment
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace_name: The namespace in which the deployment resides
        deployment_name: The name of the deployment
        container: The container to be added to the deployment
    References:
        https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/AppsV1Api.md#patch_namespaced_deployment
        https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/AppsV1Api.md#read_namespaced_deployment
    Returns:
        The patched deployment.
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_app = kubernetes.client.AppsV1Api(api_client)

        deployment_to_be_patched: V1Pod = api_instance_app.read_namespaced_deployment(name=deployment_name, namespace=namespace_name)
        pod_spec: V1DeploymentSpec = deployment_to_be_patched.spec
        deployment_containers: List[V1Container] = pod_spec.template.spec.containers
        deployment_containers.append(container)

        try:
            patched_deployment = api_instance_app.patch_namespaced_deployment(name=deployment_name, namespace=namespace_name, body=deployment_to_be_patched)
        except ApiException as error:
            logger.error("Exception when calling AppsV1Api>patch_namespaced_deployment: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return patched_deployment


def k8s_get_nodes(kube_client_config: kubernetes.client.Configuration, detailed: bool = False) -> V1NodeList | List[str]:
    """
    Return a list of nodes
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        detailed: if true, return all nodes details
    References:
        https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md#list_node
    Returns:
        The list of nodes or the list of names if detailed is false.
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        try:
            node_list: V1NodeList = api_instance_core.list_node()
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api>list_node: {}\n".format(error))
            raise error
        if detailed:
            return node_list
        else:
            name_list = []
            for item in node_list.items:
                name_list.append(item.metadata.name)
            return name_list


def k8s_add_label_to_k8s_node(kube_client_config: kubernetes.client.Configuration, node_name: str, labels: Labels) -> V1Node:
    """
    Add labels to a node
    https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md#read_node
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        node_name: The name of the node to be labeled in the cluster
        labels: labels to be applied to the node (can already exist and are overwritten)
    Returns:
        The patched node
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        node: V1Node = api_instance_core.read_node(name=node_name)

        metadata: V1ObjectMeta = node.metadata
        existing_labels: dict[str, str] = metadata.labels
        existing_labels.update(labels.labels)

        try:
            patched_node = api_instance_core.patch_node(node_name, node)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api>patch_node: {}\n".format(error))
            raise error

        return patched_node


def k8s_get_deployments(kube_client_config: kubernetes.client.Configuration, namespace: str, detailed: bool = False) -> V1DeploymentList | List[str]:
    """
    Return a list of deployments
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: the namespace in which the deployments reside
        detailed: if true, return all deployments details
    Returns:
        The list of deployments or the list of names if detailed is false.
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_apps = kubernetes.client.AppsV1Api(api_client)
        try:
            deployment_list: V1DeploymentList = api_instance_apps.list_namespaced_deployment(namespace=namespace)
        except ApiException as error:
            logger.error("Exception when calling AppsV1Api>list_namespaced_deployment: {}\n".format(error))
            raise error
        if detailed:
            return deployment_list
        else:
            name_list = []
            for item in deployment_list.items:
                name_list.append(item.metadata.name)
            return name_list


def k8s_add_label_to_k8s_deployment(kube_client_config: kubernetes.client.Configuration, namespace: str, deployment_name: str, labels: Labels) -> V1Deployment:
    """
    Add labels to a deployment
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: The namespace in which the deployment resides
        deployment_name: The name of the deployment to be labeled in the cluster
        labels: labels to be applied to the deployment (can already exist and are overwritten)
    Returns:
        The patched deployment
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_app = kubernetes.client.AppsV1Api(api_client)
        node: V1Deployment = api_instance_app.read_namespaced_deployment(namespace=namespace, name=deployment_name)

        metadata: V1ObjectMeta = node.metadata
        existing_labels: dict[str, str] = metadata.labels
        existing_labels.update(labels.labels)

        try:
            patched_node = api_instance_app.patch_namespaced_deployment(namespace=namespace, name=deployment_name, body=node)
        except ApiException as error:
            logger.error("Exception when calling AppsV1Api>read_namespaced_deployment: {}\n".format(error))
            raise error

        return patched_node


def k8s_scale_k8s_deployment(kube_client_config: kubernetes.client.Configuration, namespace: str, deployment_name: str, replica_num: int) -> V1Deployment:
    """
    Scale a deployment
    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: The namespace in which the deployment resides
        deployment_name: The name of the deployment to be labeled
        replica_num: the number of instances for the deployment
    Returns:
        The patched deployment
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_app = kubernetes.client.AppsV1Api(api_client)
        node: V1Deployment = api_instance_app.read_namespaced_deployment(namespace=namespace, name=deployment_name)

        specs: V1DeploymentSpec = node.spec
        specs.replicas = replica_num

        try:
            patched_node = api_instance_app.patch_namespaced_deployment(namespace=namespace, name=deployment_name, body=node)
        except ApiException as error:
            logger.error("Exception when calling AppsV1Api>patch_namespaced_deployment: {}\n".format(error))
            raise error

        return patched_node

def k8s_get_ipaddress_pool(kube_client_config: kubernetes.client.Configuration) -> List[str]:
    """
    Retrieve the IP address pool from the metallb.io/v1beta1 API
    Args:
        kube_client_config: the configuration of K8s on which the client is built.

    Returns:
        The list of IP addresses in the pool
    """
    ipaddress_pool = []
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_core = kubernetes.client.CustomObjectsApi(api_client)
        try:
            ipaddress_pool_list = api_instance_core.list_cluster_custom_object(group="metallb.io", version="v1beta1", plural="ipaddresspools")
            for ip_pool in ipaddress_pool_list['items']:
                pool_spec = ip_pool['spec']
                ipaddress_pool = pool_spec['addresses']
        except ApiException as error:
            logger.error("Exception when calling metallb.io/v1beta1>k8s_get_ipaddress_pool: {}\n".format(error))
            raise error
        finally:
            api_client.close()

    return ipaddress_pool

def k8s_get_storage_classes(kube_client_config: kubernetes.client.Configuration) -> V1StorageClassList:
    """
    Retrieve the storage classes from the storage.k8s.io/v1 API
    Args:
        kube_client_config: the configuration of K8s on which the client is built.

    Returns:
        The list of storage classes (V1StorageClassList)
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_core = kubernetes.client.StorageV1Api(api_client)
        try:
            return api_instance_core.list_storage_class()
        except ApiException as error:
            logger.error("Exception when calling StorageV1Api>k8s_get_storage_classes: {}\n".format(error))
            raise error
        finally:
            api_client.close()


def get_pods_for_k8s_namespace(kube_client_config: kubernetes.client.Configuration, namespace: str,
                               label_selector: str = "") -> V1PodList:
    """
    Get pods from a k8s instance that belongs to the given namespace

    Args:
        kube_client_config: kube_client_config the configuration of K8s on which the client is built.
        namespace: The namespace in witch this function looks.
        label_selector: a label selector to allow filtering on the cluster side (e.g. k8s-app=metrics-server)

    Returns:
        Return the list of pods (as V1PodList) belonging to that namespace in the given k8s cluster.
    """
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the API class
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        pod_list: V1PodList = None
        try:
            pod_list = api_instance_core.list_namespaced_pod(namespace=namespace.lower(),
                                                             label_selector=label_selector,
                                                             timeout_seconds=TIMEOUT_SECONDS)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api>list_namespaced_pod: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return pod_list


def get_logs_for_pod(kube_client_config: kubernetes.client.Configuration, namespace: str, pod_name: str, tail_lines=None) -> str:
    """
    Get logs from a pod in a k8s instance that belongs to the given namespace
    Args:
        kube_client_config: kube_client_config the configuration of K8s on which the client is built.
        namespace: The namespace in the cluster to which the pod belongs.
        pod_name: The name of the pod from which the logs are to be retrieved.
        tail_lines: The number of lines to be retrieved from the end of the log.

    Returns:
        Return the logs of the pod as a string.
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the API class
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        pod_log: str
        try:
            pod_log = api_instance_core.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=tail_lines)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api>read_namespaced_pod_log: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return pod_log


def get_daemon_sets(kube_client_config: kubernetes.client.Configuration, namespace: str = None,
                    label_selector: str = None) -> V1DaemonSetList:
    """
    Search for all DaemonSets of a namespace. If a namespace is not specified, it will work on
    all namespaces.

    Args:
        namespace: the optional namespace. If None the search is done on all namespaces.
        kube_client_config: the configuration of K8s on which the client is built.
        label_selector: The selector with witch is possible to filter the list of daemon set
        (example 'k8s-app=metrics-server')

    Returns: an object V1DaemonSetList containing a list of DaemonSets
    """
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the apps API
        api_instance_appsV1 = kubernetes.client.AppsV1Api(api_client)
        try:
            if namespace:
                daemon_set_list: V1DaemonSetList = api_instance_appsV1.list_namespaced_daemon_set(namespace=namespace,
                                                                                                  label_selector=label_selector,
                                                                                                  timeout_seconds=TIMEOUT_SECONDS)
            else:
                daemon_set_list: V1DaemonSetList = api_instance_appsV1.list_daemon_set_for_all_namespaces(
                    timeout_seconds=TIMEOUT_SECONDS)
        except ApiException as error:
            logger.error("Exception when calling appsV1->list_daemon_set: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return daemon_set_list


def get_deployments(kube_client_config: kubernetes.client.Configuration, namespace: str = None,
                    label_selector: str = None) -> V1DeploymentList:
    """
    Search for all Deployments of a namespace. If a namespace is not specified, it will work on
    all namespaces.

    Args:
        namespace: the optional namespace. If None the search is done on all namespaces.
        kube_client_config: the configuration of K8s on which the client is built.
        label_selector: The selector with witch is possible to filter the list of daemon set
        (example 'k8s-app=metrics-server')

    Returns: an object V1DaemonSetList containing a list of DaemonSets
    """
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the apps API
        api_instance_appsV1 = kubernetes.client.AppsV1Api(api_client)
        try:
            if namespace:
                deploy_list = api_instance_appsV1.list_namespaced_deployment(namespace=namespace, label_selector=label_selector)
            else:
                deploy_list: V1DeploymentList = api_instance_appsV1.list_deployment_for_all_namespaces(
                    timeout_seconds=TIMEOUT_SECONDS, label_selector=label_selector)
        except ApiException as error:
            logger.error("Exception when calling appsV1->list_deployments: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return deploy_list


def get_services(kube_client_config: kubernetes.client.Configuration, namespace: str = None,
                 label_selector: str = None) -> V1ServiceList:
    """
    Search for all Deployments of a namespace. If a namespace is not specified, it will work on
    all namespaces.

    Args:
        namespace: the optional namespace. If None the search is done on all namespaces.
        kube_client_config: the configuration of K8s on which the client is built.
        label_selector: The selector with witch is possible to filter the list of daemon set
        (example 'k8s-app=metrics-server')

    Returns: an object V1DaemonSetList containing a list of DaemonSets
    """
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the apps API
        api_instance_coreV1 = kubernetes.client.CoreV1Api(api_client)
        try:
            if namespace:
                service_list = api_instance_coreV1.list_namespaced_service(namespace=namespace, label_selector=label_selector)
            else:
                service_list: V1ServiceList = api_instance_coreV1.list_service_for_all_namespaces(timeout_seconds=TIMEOUT_SECONDS, label_selector=label_selector)
        except ApiException as error:
            logger.error("Exception when calling CoreV1->list_namespaced_service: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return service_list


def get_config_map(kube_client_config: kubernetes.client.Configuration, namespace: str, config_map_name: str) -> V1ConfigMap:
    """
        Retrieve a config map from a k8s cluster.

        Args:
            kube_client_config: the configuration of K8s on which the client is built.
            namespace: the namespace in witch the configmap is located
            config_map_name: The name of the config map

        Returns: an object V1ConfigMap containing the desired configmap if found
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_configmap = kubernetes.client.CoreV1Api(api_client)
        try:
            config_map = api_instance_configmap.read_namespaced_config_map(config_map_name, namespace=namespace)
        except ApiException as error:
            logger.error("Exception when calling CoreV1->read_namespaced_config_map: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return config_map


def patch_config_map(kube_client_config: kubernetes.client.Configuration, name, namespace, config_map: V1ConfigMap):
    """
        Patch a config map in a k8s cluster.

        Args:
            kube_client_config: the configuration of K8s on which the client is built.
            name: the name of the configmap to be patched
            namespace: the namespace in witch the configmap is located
            config_map: The configmap to be patched

        Returns: an object V1ConfigMap containing the patched configmap if patched
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_configmap = kubernetes.client.CoreV1Api(api_client)
        try:
            config_map = api_instance_configmap.patch_namespaced_config_map(name, namespace, config_map)
        except ApiException as error:
            logger.error("Exception when calling CoreV1->patch_namespaced_config_map: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return config_map


def apply_def_to_cluster(kube_client_config: kubernetes.client.Configuration, dict_to_be_applied: dict = None,
                         yaml_file_to_be_applied: Path = None):
    """
    This method can apply a definition (yaml) to a k8s cluster. The data origin to apply can be a dictionary or a yaml file.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        dict_to_be_applied: the definition (in dictionary form) to apply at the k8s cluster.
        yaml_file_to_be_applied: string. Contains the path to yaml file.

    Returns:
        [result_dict, result_yaml] the result of the definition application, a tuple of k8s resource list.
    """
    result_dict = None
    result_yaml = None

    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        try:
            if dict_to_be_applied:
                result_dict = kubernetes.utils.create_from_dict(api_client, dict_to_be_applied)
            if yaml_file_to_be_applied:
                result_yaml = create_from_yaml_custom(api_client, str(yaml_file_to_be_applied))
        except ApiException as error:
            logger.error("Exception when calling create_from_yaml: {}\n".format(error))
            raise error
        finally:
            api_client.close()
    return result_dict, result_yaml


def get_k8s_version(kube_client_config: kubernetes.client.Configuration) -> K8sVersion:
    """
    Return the k8s version of the cluster
    Args:
        kube_client_config: the configuration of K8s on which the client is built.

    Returns:
        K8sVersion: an enum containing k8s version

    Raises:
        ApiException: when an error occurs into kube client
        ValueError: When k8s version is not included among those provided
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        version_api = kubernetes.client.VersionApi(api_client)
        try:
            api_version: VersionInfo = version_api.get_code(_request_timeout=10)
        except ApiException as error:
            logger.error("Exception when calling ApisApi->get_api_versions: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        # Converting v.1.x.y -> v.1.x
        main_ver = api_version.git_version[:api_version.git_version.rfind('.')]
        if not K8sVersion.has_value(main_ver):
            raise ValueError("K8s version is not included among those provided")
        return K8sVersion(main_ver)


def get_k8s_cidr_info(kube_client_config: kubernetes.client.Configuration) -> str:
    """
    Return the pod CIDR of a k8s cluster

    Args:
        kube_client_config: the configuration of K8s on which the client is built.

    Returns:
        A String representing the pod CIDR
    """
    config_map = read_namespaced_config_map(kube_client_config=kube_client_config, config_name="kubeadm-config",
                                            namespace="kube-system")

    cluster_conf_str: str = config_map.data['ClusterConfiguration']
    cluster_conf_dict: dict = yaml.safe_load(cluster_conf_str)
    pod_subnet_str: str = cluster_conf_dict['networking']['podSubnet']

    return pod_subnet_str


def read_namespaced_config_map(kube_client_config: kubernetes.client.Configuration, namespace: str,
                               config_name: str) -> V1ConfigMap:
    """
    Read and return a config map from a namespace

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: the namespace containing the config map
        config_name: the name of the config map

    Returns:
        The desired config map in the target namespace

    Raises:
        ApiException when k8s client fail
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        core_v1_api = kubernetes.client.CoreV1Api(api_client)
        try:
            config_map: V1ConfigMap = core_v1_api.read_namespaced_config_map(name=config_name, namespace=namespace)
        except ApiException as error:
            logger.error("Exception when calling ApisApi->get_api_versions: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return config_map


def read_namespaced_storage_class(kube_client_config: kubernetes.client.Configuration, storage_class_name: str) -> V1StorageClass:
    """
    Read and return a storage class from a namespace

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        storage_class_name: the name of the storage class

    Returns:
        The V1StorageClass object representing the desired storage class in the target namespace

    Raises:
        ApiException when k8s client fails
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance = kubernetes.client.StorageV1Api(api_client)
        try:
            storage_class = api_instance.read_storage_class(name=storage_class_name)
        except kubernetes.client.rest.ApiException as error:
            logger.error(f"Exception when calling StorageV1Api->read_storage_class: {error}\n")
            raise error
        finally:
            api_client.close()

    return storage_class


def patch_namespaced_storage_class(kube_client_config: kubernetes.client.Configuration, storage_class):
    """
    Patch a storage class in a k8s cluster.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        storage_class: The storage class to be patched

    Returns:
        The patched storage class
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance = kubernetes.client.StorageV1Api(api_client)
        try:
            patched_storage_class = api_instance.patch_storage_class(name=storage_class.metadata.name,
                                                                     body=storage_class)
        except kubernetes.client.rest.ApiException as error:
            logger.error(f"Exception when calling StorageV1Api->patch_storage_class: {error}\n")
            raise error
        finally:
            api_client.close()

    return patched_storage_class

def restart_deployment(kube_client_config: kubernetes.client.Configuration, namespace: str, deployment_name: str) -> V1Deployment:
    """
    Restart a deployment by updating its annotations.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: The namespace in which the deployment resides.
        deployment_name: The name of the deployment to be restarted.

    Returns:
        The updated deployment.
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_app = kubernetes.client.AppsV1Api(api_client)
        deployment: V1Deployment = api_instance_app.read_namespaced_deployment(name=deployment_name, namespace=namespace)

        # Update the annotations to trigger a rolling restart
        if deployment.spec.template.metadata.annotations is None:
            deployment.spec.template.metadata.annotations = {}
        deployment.spec.template.metadata.annotations['nfvcl/restartedAt'] = datetime.now(timezone.utc).isoformat()

        try:
            updated_deployment = api_instance_app.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
        except ApiException as error:
            logger.error(f"Exception when calling AppsV1Api>patch_namespaced_deployment: {error}")
            raise error
        finally:
            api_client.close()

        return updated_deployment

def wait_for_deployment_to_be_ready_by_name(kube_client_config: kubernetes.client.Configuration, namespace: str, deployment_name: str, timeout: int = 300):
    """
    Wait for a deployment to be ready.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace: The namespace in which the deployment resides.
        deployment_name: The name of the deployment to wait for.
        timeout: The maximum time to wait for the deployment to be ready, in seconds.

    Returns:
        True if the deployment is ready within the timeout, False otherwise.
    """
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_app = kubernetes.client.AppsV1Api(api_client)
        start_time = time.time()

        while time.time() - start_time < timeout:
            logger.spam(f"Waiting for deployment {deployment_name} in namespace {namespace} to be ready...")
            deployment = api_instance_app.read_namespaced_deployment_status(name=deployment_name, namespace=namespace)
            if deployment.status.ready_replicas == deployment.spec.replicas:
                logger.spam(f"Deployment {deployment_name} in namespace {namespace} ready")
                return True
            time.sleep(5)
        logger.spam(f"Deployment {deployment_name} in namespace {namespace} not ready, timeout reached")
        return False

def wait_for_deployment_to_be_ready(kube_client_config: kubernetes.client.Configuration, deployment: V1Deployment, timeout: int = 300):
    """
    Wait for a deployment to be ready.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        deployment: The deployment to wait for.
        timeout: The maximum time to wait for the deployment to be ready, in seconds.

    Returns:
        True if the deployment is ready within the timeout, False otherwise.
    """

    deployment_name = deployment.metadata.name
    namespace = deployment.metadata.namespace

    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        api_instance_app = kubernetes.client.AppsV1Api(api_client)
        start_time = time.time()

        while time.time() - start_time < timeout:
            logger.spam(f"Waiting for deployment {deployment_name} in namespace {namespace} to be ready...")
            deployment_status = api_instance_app.read_namespaced_deployment_status(name=deployment_name, namespace=namespace)
            if deployment_status.spec.template.metadata.annotations == deployment.spec.template.metadata.annotations:
                if deployment_status.status.ready_replicas == deployment_status.spec.replicas:
                    logger.spam(f"Deployment {deployment_name} in namespace {namespace} ready")
                    return True
            else:
                logger.spam(f"Deployment {deployment_name} in namespace {namespace} not ready, annotations mismatch...")
            time.sleep(5)
        logger.spam(f"Deployment {deployment_name} in namespace {namespace} not ready, timeout reached")
        return False
