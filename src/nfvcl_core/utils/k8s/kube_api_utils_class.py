import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import kubernetes
import kubernetes.client
import kubernetes.utils
import yaml
from kubernetes.client import V1ServiceAccountList, ApiException, V1ServiceAccount, V1Namespace, V1NamespaceList, \
    V1ObjectMeta, V1RoleBinding, RbacV1Subject, V1RoleRef, V1Secret, V1SecretList, \
    V1CertificateSigningRequest, V1CertificateSigningRequestSpec, V1CertificateSigningRequestStatus, \
    V1CertificateSigningRequestCondition, V1Role, V1PolicyRule, V1ClusterRoleBinding, V1ResourceQuota, \
    V1ResourceQuotaSpec, V1Deployment, V1DeploymentSpec, V1NodeList, V1Node, V1Container, V1DaemonSetList, \
    V1StorageClassList, V1PodList, V1ServiceList, V1DeploymentList, V1ConfigMap, VersionInfo, V1StorageClass, \
    V1CustomResourceDefinitionList, V1RoleList
from kubernetes.stream import stream

from nfvcl_core.utils.k8s.k8s_client_extension import create_from_yaml_custom
from nfvcl_common.utils.log import create_logger
from nfvcl_common.utils.util import generate_rsa_key, generate_cert_sign_req, convert_to_base64
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.k8s_management_models import Labels
from nfvcl_core_models.topology_k8s_model import K8sQuota, K8sVersion


class KubeApiUtils:
    """
    A class for interacting with Kubernetes API
    """

    TIMEOUT_SECONDS = 10

    def __init__(self, kube_client_config: kubernetes.client.Configuration):
        """
        Initialize the KubeApiUtils with a Kubernetes client configuration.

        Args:
            kube_client_config: The configuration for Kubernetes API client
        """
        self.kube_client_config = kube_client_config
        self.logger = create_logger("K8s API utils")
        self.api_client = kubernetes.client.ApiClient(self.kube_client_config)
        self.core_v1_api = kubernetes.client.CoreV1Api(self.api_client)
        self.rbac_auth_v1_api = kubernetes.client.RbacAuthorizationV1Api(self.api_client)
        self.certificates_v1_api = kubernetes.client.CertificatesV1Api(self.api_client)
        self.apiextensions_v1_api = kubernetes.client.ApiextensionsV1Api(self.api_client)
        self.admission_registration_v1_api = kubernetes.client.AdmissionregistrationV1Api(self.api_client)
        self.custom_object_api = kubernetes.client.CustomObjectsApi(self.api_client)

    def __del__(self):
        """
        Cleanup method to close the API client when the object is destroyed
        """
        if hasattr(self, 'api_client'):
            self.api_client.close()

    def get_service_accounts(self, namespace: str = None, username: str = "") -> V1ServiceAccountList:
        """
        Retrieve all users of a namespace. If a namespace is not specified, it will work on
        all namespaces.
        There is the possibility to filter on username

        Args:
            namespace: the optional namespace. If None users are retrieved from all namespaces.
            username: the optional username to filter users.

        Returns:
            an object V1ServiceAccountList containing a list of V1AccountList
        """
        field_selector = ''
        try:
            if username != "":
                field_selector = 'metadata.name=' + username
            if namespace:
                if not self.check_namespace_exist(namespace):
                    raise NFVCLCoreException(f"Namespace ->{namespace}<- does not exist.", http_equivalent_code=404)
                service_accounts: V1ServiceAccountList = self.core_v1_api.list_namespaced_service_account(
                    namespace=namespace, field_selector=field_selector, timeout_seconds=self.TIMEOUT_SECONDS)
            else:
                service_accounts: V1ServiceAccountList = self.core_v1_api.list_service_account_for_all_namespaces(
                    field_selector=field_selector, timeout_seconds=self.TIMEOUT_SECONDS)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api in get_service_accounts: {error}", http_equivalent_code=error.status)

        return service_accounts

    def check_sa_exist(self, username: str, namespace: str = None) -> Optional[V1ServiceAccount]:
        """
        Check that a SA exist. Return None if not.
        Args:
            username: the mandatory username to filter users.
            namespace: the optional namespace. If None users are retrieved from all namespaces.
        Returns:
            The target user if found.
        """
        account_list: V1ServiceAccountList = self.get_service_accounts(namespace, username)
        if len(account_list.items) <= 0:
            if namespace:
                self.logger.debug(f"User ->{username}<- not found in namespace {namespace}")
            else:
                self.logger.debug(f"User ->{username}<- not found")
            return None
        elif len(account_list.items) == 1:
            return account_list.items[0]
        else:
            raise NFVCLCoreException(f"Not unique match for user ->{username}<- in namespace {namespace}", http_equivalent_code=409)

    def get_roles(self, namespace: str = None, rolename: str = None) -> V1RoleList:
        """
        Retrieve all roles of a namespace. If a namespace is not specified, it will work on
        all namespaces.
        There is the possibility to filter roles on role name.

        Args:
            namespace: the optional namespace. If None roles are retrieved from all namespaces.
            rolename: the optional role name to filter roles.

        Returns:
            an object V1ServiceAccountList containing a list of V1AccountList
        """
        field_selector = ''
        try:
            if rolename and rolename != "":
                field_selector = 'metadata.name=' + rolename
            if namespace and namespace != "":
                if not self.check_namespace_exist(namespace):
                    raise NFVCLCoreException(f"Namespace ->{namespace}<- does not exist.", http_equivalent_code=404)
                role_list: V1RoleList = self.rbac_auth_v1_api.list_namespaced_role(
                    namespace=namespace, field_selector=field_selector, timeout_seconds=self.TIMEOUT_SECONDS)
            else:
                role_list: V1RoleList = self.rbac_auth_v1_api.list_role_for_all_namespaces(
                    field_selector=field_selector, timeout_seconds=self.TIMEOUT_SECONDS)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling RbacAuthorizationV1Api in get_roles: {error}", http_equivalent_code=error.status)

        return role_list

    def check_role_exist(self, rolename: str, namespace: str = None) -> Optional[V1Role]:
        """
        Check that a role exists. Raise ValueError if not found or if found multiple instances.
        Args:
            rolename: the mandatory name for the role to filter roles.
            namespace: the optional namespace. If None roles are retrieved from all namespaces.
        Returns:
            The target role if found.

        Raises:
            ValueError if no role is found or if multiple roles are found
        """
        role_list: V1RoleList = self.get_roles(namespace, rolename)
        if len(role_list.items) <= 0:
            if namespace:
                self.logger.debug(f"Role ->{rolename}<- not found in namespace {namespace}")
            else:
                self.logger.debug(f"Role ->{rolename}<- not found")
            return None
        elif len(role_list.items) == 1:
            return role_list.items[0]
        else:
            raise NFVCLCoreException(f"Not unique match for role ->{rolename}<- in namespace {namespace}", http_equivalent_code=409)

    def get_namespaces(self, namespace: str = None) -> V1NamespaceList:
        """
        Retrieve all namespaces. If a namespace is specified it return that namespace.

        Args:
            namespace: the optional namespace, could lead to empty list. If absent all namespaces are retrieved.

        Returns:
            an object V1NamespaceList containing a list of namespaces. Could be empty if specified namespace does not exist.

        Raises:
            ApiException if an error occurs during the API call.
        """
        field_selector = ''
        try:
            if namespace and namespace != '':
                field_selector = 'kubernetes.io/metadata.name=' + namespace
            namespace_list: V1NamespaceList = self.core_v1_api.list_namespace(
                label_selector=field_selector,
                timeout_seconds=self.TIMEOUT_SECONDS)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api in get_namespaces: {error}", http_equivalent_code=error.status)

        return namespace_list

    def check_namespace_exist(self, namespace: str) -> Optional[V1Namespace]:
        """
        Check that a namespace exist. Raise ValueError if not found or if found multiple instance.
        Args:
            namespace: the mandatory name of namespace.
        Returns:
            The target namespace if found.

        Raises:
            ValueError if no role is found or if multiple roles are found
        """
        namespace_list: V1NamespaceList = self.get_namespaces(namespace)
        if len(namespace_list.items) <= 0:
            self.logger.debug(f"Namespace ->{namespace}<- not found")
            return None
        elif len(namespace_list.items) == 1:
            return namespace_list.items[0]
        else:
            raise NFVCLCoreException(f"Not unique match for namespace ->{namespace}<-", http_equivalent_code=409)

    def create_service_account(self, namespace: str, username: str) -> V1ServiceAccount:
        """
        Create a service account in a namespace

        Args:
            namespace: the mandatory namespace in witch the service account is created
            username: the name of the service account

        Returns:
            The created service account
        """
        try:
            metadata: V1ObjectMeta = V1ObjectMeta(name=username, namespace=namespace)
            sa: V1ServiceAccount = V1ServiceAccount(metadata=metadata)
            created_sa: V1ServiceAccount = self.core_v1_api.create_namespaced_service_account(namespace, body=sa)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api in create_service_account: {error}", http_equivalent_code=error.status)

        return created_sa

    def create_admin_role(self, namespace: str) -> V1Role:
        """
        Create an admin role called 'admin' in a namespace. If it exists, it will get the admin role from the namespace.
        Args:
            namespace: The namespace where to create the admin role
        Returns:
            The created role
        Raises:
            ValueError if the namespace doesn't exist
        """
        if not self.check_namespace_exist(namespace):
            raise NFVCLCoreException(f"Namespace ->{namespace}<- does not exist.", http_equivalent_code=404)
        try:
            metadata: V1ObjectMeta = V1ObjectMeta(name="admin")
            # Admin role
            rules = [V1PolicyRule(api_groups=['*'], resources=['*'], verbs=['*'])]
            role = V1Role(rules=rules, metadata=metadata)
            role_res: V1Role = self.rbac_auth_v1_api.create_namespaced_role(namespace=namespace, body=role)
        except ApiException as error:
            if error.status == 409:
                self.logger.warning(f"Role ->admin<- already exist in namespace ->{namespace}<-")
                return self.rbac_auth_v1_api.list_namespaced_role(namespace=namespace, field_selector='metadata.name=admin').items[0]
            else:
                raise NFVCLCoreException(f"Exception when calling CoreV1Api in create_admin_role: {error}", http_equivalent_code=error.status)
        return role_res

    def admin_role_to_sa(self, namespace: str, username: str, role_binding_name: str) -> V1RoleBinding:
        """
        Give to an EXISTING service account the admin role on a namespace.
        Args:
            namespace: the target namespace where the user resides
            username: the name of the service account that will become administrator of the namespace
            role_binding_name: the name that will be given to the rule.

        Returns:
            The created role binding to administrator.
        """
        if not self.check_namespace_exist(namespace):
            raise NFVCLCoreException(f"Namespace ->{namespace}<- does not exist.", http_equivalent_code=404)
        if not self.check_sa_exist(username, namespace):
            raise NFVCLCoreException(f"User ->{username}<- not found in {namespace} namespace.", http_equivalent_code=404)
        if not self.check_role_exist("admin", namespace):
            self.create_admin_role(namespace)
        try:
            metadata: V1ObjectMeta = V1ObjectMeta(name=role_binding_name)

            subjects = [RbacV1Subject(kind='ServiceAccount', name=username)]
            role_ref = V1RoleRef(kind='Role', name='admin', api_group='rbac.authorization.k8s.io')

            role_bind = V1RoleBinding(subjects=subjects, role_ref=role_ref, metadata=metadata)
            role_bind_res: V1RoleBinding = self.rbac_auth_v1_api.create_namespaced_role_binding(
                namespace=namespace, body=role_bind)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling RbacAuthorizationV1Api in admin_role_to_sa: {error}", http_equivalent_code=error.status)

        return role_bind_res

    def cluster_admin_to_sa(self, username: str, namespace: str, role_binding_name: str) -> V1ClusterRoleBinding:
        """
        This function is specific to give CLUSTER admin rights to a Service Account.

        Args:
            username: the name of the user that will become cluster administrator
            role_binding_name: the name that will be given to the cluister role binding.

        Returns:
            The created cluster role binding for administrator.
        """
        try:
            metadata: V1ObjectMeta = V1ObjectMeta(name=role_binding_name)

            subjects = [RbacV1Subject(kind='ServiceAccount', name=username, namespace=namespace)]
            role_ref = V1RoleRef(kind='ClusterRole', name='cluster-admin', api_group='rbac.authorization.k8s.io')

            role_bind = V1ClusterRoleBinding(subjects=subjects, role_ref=role_ref, metadata=metadata)
            role_bind_res: V1ClusterRoleBinding = self.rbac_auth_v1_api.create_cluster_role_binding(body=role_bind)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api in cluster_admin: {error}", http_equivalent_code=error.status)

        return role_bind_res

    def create_secret_for_user(self, namespace: str, username: str, secret_name: str) -> V1Secret:
        """
        Create a secret for a user.
        Args:
            namespace: The namespace where the user reside
            username: The user to which the secret is assigned
            secret_name: The name given at the secret

        Returns:
            The created secret
        """
        if not self.check_namespace_exist(namespace):
            raise NFVCLCoreException(f"Namespace ->{namespace}<- does not exist.", http_equivalent_code=404)
        service_account: V1ServiceAccount = self.check_sa_exist(username, namespace)
        if not service_account:
            raise NFVCLCoreException(f"User ->{username}<- not found in {namespace} namespace.", http_equivalent_code=404)

        try:
            annotations = {'kubernetes.io/service-account.name': username}
            metadata: V1ObjectMeta = V1ObjectMeta(name=secret_name, annotations=annotations)

            auth_req = V1Secret(metadata=metadata, type="kubernetes.io/service-account-token")
            auth_resp: V1Secret = self.core_v1_api.create_namespaced_secret(namespace=namespace, body=auth_req)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api in create_secret_for_user: {error}", http_equivalent_code=error.status)

        return auth_resp

    def get_secrets(self, namespace: str = "", secret_name: str = "", owner: str = "") -> V1SecretList:
        """
        Retrieve secrets from k8s cluster

        Args:
            namespace: optional to filter secrets on namespace
            secret_name: optional to filter secrets on their name
            owner: optional to filter secrets on the owner

        Returns:
            A filtered list of secrets
        """
        field_selector = ''
        try:
            if secret_name != "":
                field_selector = 'metadata.name=' + secret_name

            if namespace != "":
                if not self.check_namespace_exist(namespace):
                    raise NFVCLCoreException(f"Namespace ->{namespace}<- does not exist.", http_equivalent_code=404)
                secret_list: V1SecretList = self.core_v1_api.list_namespaced_secret(
                    namespace=namespace, field_selector=field_selector)
            else:
                secret_list: V1SecretList = self.core_v1_api.list_secret_for_all_namespaces(
                    field_selector=field_selector)

            # Filter by owner if specified
            to_return_list = []
            if owner != "":
                for secret in secret_list.items:
                    annotations: dict = secret.metadata.annotations
                    if annotations is not None:
                        if 'kubernetes.io/service-account.name' in annotations.keys():
                            if annotations['kubernetes.io/service-account.name'] == owner:
                                to_return_list.append(secret)
                secret_list.items = to_return_list

        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api in get_secrets: {error}", http_equivalent_code=error.status)

        return secret_list

    def cert_sign_req(self, username: str, expiration_sec: int = 63072000) -> dict:
        """
        Create a certificate signing request and approve it

        Args:
            username: The username for the certificate
            expiration_sec: Certificate expiration time in seconds (default: 2 years)

        Returns:
            Dictionary with certificate details
        """
        key, private_key = generate_rsa_key()
        # IMPORTANT the username inside cert will be the username arriving at the API server!
        # When giving permissions with binding roles, this is the subject!
        cert_sign_req = generate_cert_sign_req(username, key)
        cert_sign_req_base64 = convert_to_base64(cert_sign_req)

        try:
            # CSR
            usages = ["client auth"]
            csr_spec = V1CertificateSigningRequestSpec(request=cert_sign_req_base64,
                                                       signer_name='kubernetes.io/kube-apiserver-client',
                                                       expiration_seconds=expiration_sec, usages=usages)

            metadata = V1ObjectMeta(name=username)
            v1csr = V1CertificateSigningRequest(spec=csr_spec, metadata=metadata)
            csr_result: V1CertificateSigningRequest = self.certificates_v1_api.create_certificate_signing_request(body=v1csr)

            condition = V1CertificateSigningRequestCondition(message="This CSR was approved by NFVCL",
                                                             reason="NFVCL Kubectl user",
                                                             status="True",
                                                             type="Approved")
            conditions = [condition]
            status = V1CertificateSigningRequestStatus(conditions=conditions)
            csr_result.status = status
            self.certificates_v1_api.patch_certificate_signing_request_approval(
                name=username, body=csr_result)
            # Need to sleep otherwise the cert is still not ready
            time.sleep(0.10)
            csr_result: V1CertificateSigningRequest = self.certificates_v1_api.read_certificate_signing_request(
                name=username)

            ############ GET cluster certificate ##########
            cm_list = self.core_v1_api.list_namespaced_config_map(namespace="default")
            ca_root = [item for item in cm_list.items if item.metadata.name == 'kube-root-ca.crt']
            if len(ca_root) <= 0:
                self.logger.error("No kube-root-ca.crt found in the cluster")

            ca_root_data = ca_root[0].data['ca.crt']
        except (ValueError, ApiException) as error:
            self.logger.error(f"Exception when calling CertificatesV1Api in cert_sign_req: {error}")
            raise error

        # Making private key clean from PEM embedding and '\n'
        private_key_base64 = convert_to_base64(private_key)
        ca_root_data_b64 = convert_to_base64(str.encode(ca_root_data))

        to_return = {"cluster_cert": ca_root_data_b64,
                     "user_key_b64": private_key_base64,
                     "user_priv_cert_b64": csr_result.status.certificate,
                     "csr_approved": csr_result.to_dict()}

        return to_return

    def create_namespace(self, namespace_name: str, labels: dict) -> V1Namespace:
        """
        Create a namespace in a k8s cluster.

        Args:
            namespace_name: The name of the namespace to be created
            labels: The labels to be assigned to the namespace

        Returns:
            The created namespace
        """
        try:
            metadata = V1ObjectMeta(name=namespace_name, labels=labels)
            namespace_body = V1Namespace(metadata=metadata)
            namespace = self.core_v1_api.create_namespace(body=namespace_body)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>create_namespace: {error}", http_equivalent_code=error.status)

        return namespace

    def delete_namespace(self, namespace_name: str) -> V1Namespace:
        """
        Delete a namespace in a k8s cluster.

        Args:
            namespace_name: The name of the namespace to be deleted

        Returns:
            The deleted namespace
        """
        try:
            namespace = self.core_v1_api.delete_namespace(name=namespace_name)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>delete_namespace: {error}", http_equivalent_code=error.status)

        return namespace

    def delete_mutating_webhook_configuration(self, mutating_webook_configuration_name: str) -> V1Namespace:
        """
        Delete a MutatingWebhookConfiguration in a k8s cluster.

        Args:
            mutating_webook_configuration_name: The name of the MutatingWebhookConfiguration to be deleted

        Returns:
            The deleted namespace
        """
        try:
            mwc = self.admission_registration_v1_api.delete_mutating_webhook_configuration(mutating_webook_configuration_name)
        except ApiException as error:
            self.logger.error(f"Exception when calling AdmissionregistrationV1Api>delete_mutating_webhook_configuration: {error}")
            raise error

        return mwc

    def add_quota_to_namespace(self, namespace_name: str, quota_name: str, quota: K8sQuota) -> V1ResourceQuota:
        """
        Add a quota (for resources) to the namespace

        Args:
            namespace_name: The namespace on witch the quota is applied
            quota_name: The name of the quota reservation
            quota: The quantities to be reserved

        Returns:
            The created quota.
        """
        try:
            spec = quota.model_dump(by_alias=True, exclude_none=True)
            res_spec = V1ResourceQuotaSpec(hard=spec)
            metadata = V1ObjectMeta(name=quota_name)
            res_quota = V1ResourceQuota(metadata=metadata, spec=res_spec)

            created_quota = self.core_v1_api.create_namespaced_resource_quota(namespace=namespace_name, body=res_quota)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>add_quota_to_namespace: {error}", http_equivalent_code=error.status)

        return created_quota

    def add_container_to_namespaced_deployment(self, namespace_name: str, deployment_name: str, container: V1Container) -> V1Deployment:
        """
        Add a container to the deployment. Can be used to inject sidecars into Pods of a Deployment

        Args:
            namespace_name: The namespace in which the deployment resides
            deployment_name: The name of the deployment
            container: The container to be added to the deployment

        References:
            https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/AppsV1Api.md#patch_namespaced_deployment
            https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/AppsV1Api.md#read_namespaced_deployment

        Returns:
            The patched deployment.
        """
        apps_v1_api = kubernetes.client.AppsV1Api(self.api_client)

        try:
            deployment_to_be_patched: V1Deployment = apps_v1_api.read_namespaced_deployment(
                name=deployment_name, namespace=namespace_name)
            pod_spec: V1DeploymentSpec = deployment_to_be_patched.spec
            deployment_containers: List[V1Container] = pod_spec.template.spec.containers
            deployment_containers.append(container)

            patched_deployment = apps_v1_api.patch_namespaced_deployment(
                name=deployment_name, namespace=namespace_name, body=deployment_to_be_patched)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling AppsV1Api>add_container_to_namespaced_deployment: {error}", http_equivalent_code=error.status)

        return patched_deployment

    def get_nodes(self, detailed: bool = False) -> V1NodeList | List[str]:
        """
        Return a list of nodes
self.rbac_auth_v1_api.list_namespaced_role(namespace=namespace, field_selector='metadata.name=admin')
        Args:
            detailed: if true, return all nodes details

        References:
            https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md#list_node

        Returns:
            The list of nodes or the list of names if detailed is false.
        """
        try:
            node_list: V1NodeList = self.core_v1_api.list_node()

            if detailed:
                return node_list
            else:
                name_list = []
                for item in node_list.items:
                    name_list.append(item.metadata.name)
                return name_list
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>get_nodes: {error}", http_equivalent_code=error.status)

    def add_label_to_k8s_node(self, node_name: str, labels: Labels) -> V1Node:
        """
        Add labels to a node

        Args:
            node_name: The name of the node to be labeled in the cluster
            labels: labels to be applied to the node (can already exist and are overwritten)

        Returns:
            The patched node
        """
        try:
            node: V1Node = self.core_v1_api.read_node(name=node_name)

            metadata: V1ObjectMeta = node.metadata
            existing_labels: dict[str, str] = metadata.labels
            existing_labels.update(labels.labels)

            patched_node = self.core_v1_api.patch_node(node_name, node)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>add_label_to_k8s_node: {error}", http_equivalent_code=error.status)

        return patched_node

    def get_deployments(self, namespace: str, detailed: bool = False) -> V1DeploymentList | List[str]:
        """
        Return a list of deployments

        Args:
            namespace: the namespace in which the deployments reside
            detailed: if true, return all deployments details

        Returns:
            The list of deployments or the list of names if detailed is false.
        """
        apps_v1_api = kubernetes.client.AppsV1Api(self.api_client)

        try:
            deployment_list: V1DeploymentList = apps_v1_api.list_namespaced_deployment(namespace=namespace)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling AppsV1Api>get_deployments: {error}", http_equivalent_code=error.status)
        if detailed:
            return deployment_list
        else:
            name_list = []
            for item in deployment_list.items:
                name_list.append(item.metadata.name)
            return name_list

    def add_label_to_k8s_deployment(self, namespace: str, deployment_name: str, labels: Labels) -> V1Deployment:
        """
        Add labels to a deployment

        Args:
            namespace: The namespace in which the deployment resides
            deployment_name: The name of the deployment to be labeled in the cluster
            labels: labels to be applied to the deployment (can already exist and are overwritten)

        Returns:
            The patched deployment
        """
        apps_v1_api = kubernetes.client.AppsV1Api(self.api_client)

        try:
            deployment: V1Deployment = apps_v1_api.read_namespaced_deployment(
                namespace=namespace, name=deployment_name)

            metadata: V1ObjectMeta = deployment.metadata
            existing_labels: dict[str, str] = metadata.labels
            existing_labels.update(labels.labels)

            patched_deployment = apps_v1_api.patch_namespaced_deployment(
                namespace=namespace, name=deployment_name, body=deployment)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling AppsV1Api>add_label_to_k8s_deployment: {error}", http_equivalent_code=error.status)
        return patched_deployment

    def scale_k8s_deployment(self, namespace: str, deployment_name: str, replica_num: int) -> V1Deployment:
        """
        Scale a deployment

        Args:
            namespace: The namespace in which the deployment resides
            deployment_name: The name of the deployment to be labeled
            replica_num: the number of instances for the deployment

        Returns:
            The patched deployment
        """
        apps_v1_api = kubernetes.client.AppsV1Api(self.api_client)

        try:
            deployment: V1Deployment = apps_v1_api.read_namespaced_deployment(
                namespace=namespace, name=deployment_name)

            spec: V1DeploymentSpec = deployment.spec
            spec.replicas = replica_num

            patched_deployment = apps_v1_api.patch_namespaced_deployment(
                namespace=namespace, name=deployment_name, body=deployment)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling AppsV1Api>scale_k8s_deployment: {error}", http_equivalent_code=error.status)

        return patched_deployment

    def get_services(self, namespace: str = None, label_selector: str = None) -> V1ServiceList:
        """
        Search for all Services in a namespace. If a namespace is not specified, it will work on
        all namespaces.

        Args:
            namespace: the optional namespace. If None the search is done on all namespaces.
            label_selector: The selector with which is possible to filter the list of services
                (example 'app=nginx')

        Returns:
            An object V1ServiceList containing a list of Services
        """
        try:
            if namespace:
                service_list = self.core_v1_api.list_namespaced_service(
                    namespace=namespace,
                    label_selector=label_selector,
                    timeout_seconds=self.TIMEOUT_SECONDS)
            else:
                service_list = self.core_v1_api.list_service_for_all_namespaces(
                    label_selector=label_selector,
                    timeout_seconds=self.TIMEOUT_SECONDS)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>get_services: {error}", http_equivalent_code=error.status)

        return service_list

    def get_pods_for_namespace(self, namespace: str, label_selector: str = "") -> V1PodList:
        """
        Get pods from a k8s instance that belongs to the given namespace

        Args:
            namespace: The namespace in which this function looks.
            label_selector: a label selector to allow filtering on the cluster side (e.g. k8s-app=metrics-server)

        Returns:
            Return the list of pods (as V1PodList) belonging to that namespace in the given k8s cluster.
        """
        try:
            pod_list = self.core_v1_api.list_namespaced_pod(
                namespace=namespace.lower(),
                label_selector=label_selector,
                timeout_seconds=self.TIMEOUT_SECONDS)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>get_pods_for_namespace: {error}", http_equivalent_code=error.status)

        return pod_list

    def get_logs_for_pod(self, namespace: str, pod_name: str, tail_lines=None) -> str:
        """
        Get logs from a pod in a k8s instance that belongs to the given namespace

        Args:
            namespace: The namespace in the cluster to which the pod belongs.
            pod_name: The name of the pod from which the logs are to be retrieved.
            tail_lines: The number of lines to be retrieved from the end of the log.

        Returns:
            Return the logs of the pod as a string.
        """
        try:
            pod_log = self.core_v1_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=tail_lines)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>get_logs_for_pod: {error}", http_equivalent_code=error.status)
        return pod_log

    def get_daemon_sets(self, namespace: str = None, label_selector: str = None) -> V1DaemonSetList:
        """
        Search for all DaemonSets of a namespace. If a namespace is not specified, it will work on
        all namespaces.

        Args:
            namespace: the optional namespace. If None the search is done on all namespaces.
            label_selector: The selector with which is possible to filter the list of daemon sets
                (example 'k8s-app=metrics-server')

        Returns:
            An object V1DaemonSetList containing a list of DaemonSets
        """
        apps_v1_api = kubernetes.client.AppsV1Api(self.api_client)

        try:
            if namespace:
                daemon_set_list = apps_v1_api.list_namespaced_daemon_set(
                    namespace=namespace,
                    label_selector=label_selector,
                    timeout_seconds=self.TIMEOUT_SECONDS)
            else:
                daemon_set_list = apps_v1_api.list_daemon_set_for_all_namespaces(
                    timeout_seconds=self.TIMEOUT_SECONDS)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling AppsV1Api>get_daemon_sets: {error}", http_equivalent_code=error.status)

        return daemon_set_list

    def get_ipaddress_pool(self) -> List[str]:
        """
        Retrieve the IP address pool from the metallb.io/v1beta1 API

        Returns:
            The list of IP addresses in the pool
        """
        custom_objects_api = kubernetes.client.CustomObjectsApi(self.api_client)
        ipaddress_pool = []

        try:
            ipaddress_pool_list = custom_objects_api.list_cluster_custom_object(
                group="metallb.io",
                version="v1beta1",
                plural="ipaddresspools")

            for ip_pool in ipaddress_pool_list['items']:
                pool_spec = ip_pool['spec']
                ipaddress_pool = pool_spec['addresses']
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CustomObjectsApi>get_ipaddress_pool: {error}", http_equivalent_code=error.status)

        return ipaddress_pool

    def get_storage_classes(self) -> V1StorageClassList:
        """
        Retrieve the storage classes from the storage.k8s.io/v1 API

        Returns:
            The list of storage classes (V1StorageClassList)
        """
        storage_v1_api = kubernetes.client.StorageV1Api(self.api_client)

        try:
            return storage_v1_api.list_storage_class()
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling StorageV1Api>get_storage_classes: {error}", http_equivalent_code=error.status)

    def restart_deployment(self, namespace: str, deployment_name: str) -> V1Deployment:
        """
        Restart a deployment by updating its annotations.

        Args:
            namespace: The namespace in which the deployment resides.
            deployment_name: The name of the deployment to be restarted.

        Returns:
            The updated deployment.
        """

        apps_v1_api = kubernetes.client.AppsV1Api(self.api_client)
        deployment: V1Deployment = apps_v1_api.read_namespaced_deployment(name=deployment_name, namespace=namespace)

        # Update the annotations to trigger a rolling restart
        if deployment.spec.template.metadata.annotations is None:
            deployment.spec.template.metadata.annotations = {}
        deployment.spec.template.metadata.annotations['nfvcl/restartedAt'] = datetime.now(timezone.utc).isoformat()

        try:
            updated_deployment = apps_v1_api.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling AppsV1Api>restart_deployment: {error}", http_equivalent_code=error.status)

        return updated_deployment

    def wait_for_deployment_to_be_ready_by_name(self, namespace: str, deployment_name: str, timeout: int = 300) -> bool:
        """
        Wait for a deployment to be ready.

        Args:
            namespace: The namespace in which the deployment resides.
            deployment_name: The name of the deployment to wait for.
            timeout: The maximum time to wait for the deployment to be ready, in seconds.

        Returns:
            True if the deployment is ready within the timeout, False otherwise.
        """
        apps_v1_api = kubernetes.client.AppsV1Api(self.api_client)
        start_time = time.time()

        while time.time() - start_time < timeout:
            self.logger.debug(f"Waiting for deployment {deployment_name} in namespace {namespace} to be ready...")
            deployment = apps_v1_api.read_namespaced_deployment_status(name=deployment_name, namespace=namespace)
            if deployment.status.ready_replicas == deployment.spec.replicas:
                self.logger.debug(f"Deployment {deployment_name} in namespace {namespace} ready")
                return True
            time.sleep(5)

        self.logger.warning(f"Deployment {deployment_name} in namespace {namespace} not ready, timeout reached")
        return False

    def wait_for_deployment_to_be_ready(self, deployment: V1Deployment, timeout: int = 300) -> bool:
        """
        Wait for a deployment to be ready.

        Args:
            deployment: The deployment to wait for.
            timeout: The maximum time to wait for the deployment to be ready, in seconds.

        Returns:
            True if the deployment is ready within the timeout, False otherwise.
        """
        deployment_name = deployment.metadata.name
        namespace = deployment.metadata.namespace

        apps_v1_api = kubernetes.client.AppsV1Api(self.api_client)
        start_time = time.time()

        while time.time() - start_time < timeout:
            self.logger.debug(f"Waiting for deployment {deployment_name} in namespace {namespace} to be ready...")
            deployment_status = apps_v1_api.read_namespaced_deployment_status(name=deployment_name, namespace=namespace)
            if deployment_status.spec.template.metadata.annotations == deployment.spec.template.metadata.annotations:
                if deployment_status.status.ready_replicas == deployment_status.spec.replicas:
                    self.logger.debug(f"Deployment {deployment_name} in namespace {namespace} ready")
                    return True
            else:
                self.logger.debug(f"Deployment {deployment_name} in namespace {namespace} not ready, annotations mismatch...")
            time.sleep(5)

        self.logger.warning(f"Deployment {deployment_name} in namespace {namespace} not ready, timeout reached")
        return False

    def apply_def_to_cluster(self, dict_to_be_applied: dict = None, yaml_file_to_be_applied: Path = None):
        """
        This method can apply a definition (yaml) to a k8s cluster. The data origin to apply can be a dictionary or a yaml file.

        Args:
            dict_to_be_applied: the definition (in dictionary form) to apply at the k8s cluster.
            yaml_file_to_be_applied: string. Contains the path to yaml file.

        Returns:
            [result_dict, result_yaml] the result of the definition application, a tuple of k8s resource list.
        """
        result_dict = None
        result_yaml = None

        try:
            if dict_to_be_applied:
                result_dict = kubernetes.utils.create_from_dict(self.api_client, dict_to_be_applied)
            if yaml_file_to_be_applied:
                result_yaml = create_from_yaml_custom(self.api_client, str(yaml_file_to_be_applied))
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>apply_def_to_cluster: {error}", http_equivalent_code=error.status)
        return result_dict, result_yaml

    def get_cidr_info(self) -> str:
        """
        Return the pod CIDR of a k8s cluster

        Returns:
            A String representing the pod CIDR
        """
        config_map = self.read_namespaced_config_map(config_name="kubeadm-config", namespace="kube-system")

        cluster_conf_str: str = config_map.data['ClusterConfiguration']
        cluster_conf_dict: dict = yaml.safe_load(cluster_conf_str)
        pod_subnet_str: str = cluster_conf_dict['networking']['podSubnet']

        return pod_subnet_str

    def read_namespaced_config_map(self, namespace: str, config_name: str) -> V1ConfigMap:
        """
        Read and return a config map from a namespace

        Args:
            namespace: the namespace containing the config map
            config_name: the name of the config map

        Returns:
            The desired config map in the target namespace

        Raises:
            ApiException when k8s client fail
        """
        try:
            config_map: V1ConfigMap = self.core_v1_api.read_namespaced_config_map(name=config_name, namespace=namespace)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>read_namespaced_config_map: {error}", http_equivalent_code=error.status)

        return config_map

    def get_k8s_version(self) -> K8sVersion:
        """
        Return the k8s version of the cluster

        Returns:
            K8sVersion: an enum containing k8s version

        Raises:
            ApiException: when an error occurs into kube client
            ValueError: When k8s version is not included among those provided
        """
        version_api = kubernetes.client.VersionApi(self.api_client)
        try:
            api_version: VersionInfo = version_api.get_code(_request_timeout=10)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling VersionApi>get_code: {error}", http_equivalent_code=error.status)

        # Converting v.1.x.y -> v.1.x
        main_ver = api_version.git_version[:api_version.git_version.rfind('.')]
        if not K8sVersion.has_value(main_ver):
            raise ValueError("K8s version is not included among those provided")
        return K8sVersion(main_ver)

    def read_namespaced_storage_class(self, storage_class_name: str) -> V1StorageClass:
        """
        Read and return a storage class from a namespace

        Args:
            storage_class_name: the name of the storage class

        Returns:
            The V1StorageClass object representing the desired storage class in the target namespace

        Raises:
            ApiException when k8s client fails
        """
        api_instance = kubernetes.client.StorageV1Api(self.api_client)
        try:
            storage_class = api_instance.read_storage_class(name=storage_class_name)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling StorageV1Api>read_namespaced_storage_class: {error}", http_equivalent_code=error.status)

        return storage_class

    def patch_namespaced_storage_class(self, storage_class) -> V1StorageClass:
        """
        Patch a storage class in a k8s cluster.

        Args:
            storage_class: The storage class to be patched

        Returns:
            The patched storage class
        """
        api_instance = kubernetes.client.StorageV1Api(self.api_client)
        try:
            patched_storage_class = api_instance.patch_storage_class(name=storage_class.metadata.name, body=storage_class)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling StorageV1Api>patch_namespaced_storage_class: {error}", http_equivalent_code=error.status)

        return patched_storage_class

    def get_config_map(self, namespace: str, config_map_name: str) -> V1ConfigMap:
        """
        Retrieve a config map from a k8s cluster.

        Args:
            namespace: the namespace in witch the configmap is located
            config_map_name: The name of the config map

        Returns: an object V1ConfigMap containing the desired configmap if found
        """
        try:
            config_map = self.core_v1_api.read_namespaced_config_map(config_map_name, namespace=namespace)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>get_config_map: {error}", http_equivalent_code=error.status)

        return config_map

    def patch_config_map(self, name, namespace, config_map: V1ConfigMap) -> V1ConfigMap:
        """
        Patch a config map in a k8s cluster.

        Args:
            name: the name of the configmap to be patched
            namespace: the namespace in witch the configmap is located
            config_map: The configmap to be patched

        Returns: an object V1ConfigMap containing the patched configmap if patched
        """
        try:
            config_map = self.core_v1_api.patch_namespaced_config_map(name, namespace, config_map)
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling CoreV1Api>patch_config_map: {error}", http_equivalent_code=error.status)

        return config_map

    def get_custom_resource_definitions(self, detailed: bool = False) -> V1CustomResourceDefinitionList | List[str]:
        """
        Get a list of all Custom Resource Definitions (CRDs) in the cluster.
        Equivalent to running 'kubectl get crds' command.

        Args:
            detailed: If True, returns the complete V1CustomResourceDefinitionList object.
                     If False, returns just a list of CRD names.

        Returns:
            Either the complete V1CustomResourceDefinitionList object (if detailed=True),
            or just a list of CRD names (if detailed=False).

        Raises:
            ApiException: If there's an error in the API call
        """
        try:
            crd_list = self.apiextensions_v1_api.list_custom_resource_definition(
                timeout_seconds=self.TIMEOUT_SECONDS
            )

            if detailed:
                return crd_list
            else:
                name_list = []
                for item in crd_list.items:
                    name_list.append(item.metadata.name)
                return name_list
        except ApiException as error:
            raise NFVCLCoreException(f"Exception when calling ApiextensionsV1Api>get_custom_resource_definitions: {error}", http_equivalent_code=error.status)

    def restart_all_deployments(self, namespace: str) -> List[V1Deployment]:
        """
        Restart all deployments in a namespace.

        Args:
            namespace: The namespace in which the deployment resides.

        Returns:
            The updated deployments.
        """
        api_instance_app = kubernetes.client.AppsV1Api(self.api_client)
        deployments: V1DeploymentList = api_instance_app.list_namespaced_deployment(namespace=namespace.lower())
        updated_deployments: List[V1Deployment] = []

        # Iterate over each deployment and trigger a rolling restart
        for deployment in deployments.items:
            deployment_name = deployment.metadata.name

            if deployment.spec.template.metadata.annotations is None:
                deployment.spec.template.metadata.annotations = {}
            deployment.spec.template.metadata.annotations['nfvcl/restartedAt'] = datetime.now(timezone.utc).isoformat()

            try:
                updated_deployment = api_instance_app.patch_namespaced_deployment(name=deployment_name, namespace=namespace.lower(), body=deployment)
                updated_deployments.append(updated_deployment)
            except ApiException as error:
                self.logger.error(f"Exception when calling AppsV1Api>patch_namespaced_deployment: {error}")
                raise error

        return updated_deployments

    def exec_command_in_pod(self, namespace, command, pod_name=None, container_name=None) -> str:
        """
        Executes an arbitrary command in a specified container in a pod.

        :param namespace: Namespace of the pod
        :param pod_name: Name of the pod
        :param container_name: Name of the container in the pod
        :param command: List of strings representing the command and args (example ['ls', '-l'])
        :return: The stdout and stderr output of the command
        """

        if pod_name is None:
            pods = self.core_v1_api.list_namespaced_pod(namespace=namespace)
            pod_name = [pod.metadata.name for pod in pods.items][0]

        resp = stream(self.core_v1_api.connect_get_namespaced_pod_exec,
                      name=pod_name,
                      namespace=namespace,
                      container=container_name,
                      command=command,
                      stderr=True,
                      stdin=False,
                      stdout=True,
                      tty=False)

        return resp


    def remove_alloy_finalizier(self, namespace: str):
        """
        !!! WARNING !!!
        This method is a working around for a bug of K8s_monitoring helmchart, its WIP the patch
        Args:
            namespace: namespace of the pod

        """
        # List all CRDs
        crds = self.apiextensions_v1_api.list_custom_resource_definition()
        for crd in crds.items:
            if crd.spec.names.kind == "Alloy":
                version = [v.name for v in crd.spec.versions][0]
                _group = crd.spec.group
                plural = crd.spec.names.plural
                custom_objs = self.custom_object_api.list_namespaced_custom_object(_group, version, namespace, plural)
                for obj in custom_objs.get("items", []):
                    name = obj["metadata"]["name"]
                    self.custom_object_api.patch_namespaced_custom_object(
                        group=_group,
                        version=version,
                        namespace=namespace,
                        plural=plural,
                        name=name,
                        body={"metadata": {"finalizers": []}}
                    )
