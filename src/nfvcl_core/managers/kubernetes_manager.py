from typing import List

from kubernetes.client import V1PodList, V1Namespace, ApiException, V1ServiceAccountList, V1ClusterRoleList, V1NamespaceList, V1RoleBinding, V1ClusterRoleBinding, V1ServiceAccount, V1Secret, V1SecretList, V1ResourceQuota, V1NodeList, V1Node, V1DeploymentList, V1Deployment
from kubernetes.utils import FailToCreateError

from nfvcl.models.k8s.common_k8s_model import Labels
from nfvcl.models.k8s.plugin_k8s_model import K8sPluginName, K8sPluginsToInstall, K8sLoadBalancerPoolArea, K8sPluginAdditionalData
from nfvcl.models.k8s.topology_k8s_model import TopologyK8sModel, K8sQuota
from nfvcl_core.utils.k8s import get_k8s_config_from_file_content, get_k8s_cidr_info, get_pods_for_k8s_namespace, k8s_create_namespace, k8s_delete_namespace, apply_def_to_cluster
from nfvcl_core.utils.k8s.helm_plugin_manager import HelmPluginManager
from nfvcl_core.utils.k8s.kube_api_utils import get_service_accounts, k8s_get_roles, get_k8s_namespaces, k8s_admin_role_to_sa, k8s_admin_role_over_namespace, k8s_cluster_admin, k8s_create_service_account, k8s_create_secret_for_user, k8s_get_secrets, k8s_cert_sign_req, k8s_add_quota_to_namespace, k8s_get_nodes, k8s_add_label_to_k8s_node, k8s_get_deployments, k8s_add_label_to_k8s_deployment, k8s_scale_k8s_deployment, k8s_get_ipaddress_pool, k8s_get_storage_classes
from nfvcl_core.managers import TopologyManager, BlueprintManager, EventManager
from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core.models.response_model import OssCompliantResponse, OssStatus
from nfvcl_core.utils.blue_utils import yaml


class KubernetesManager(GenericManager):
    def __init__(self, topology_manager: TopologyManager, blueprint_manager: BlueprintManager, event_manager: EventManager):
        super().__init__()
        self._topology_manager = topology_manager
        self._blueprint_manager = blueprint_manager
        self._event_manager = event_manager


    def get_k8s_installed_plugins(self, cluster_id: str) -> List[K8sPluginName]:
        """
        Return installed plugins on a cluster

        Args:

            cluster_id: [str] the cluster id

        Returns:

            A list of installed plugins
        """
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        helm_plugin_manager = HelmPluginManager(cluster.credentials, "K8S REST UTILS")
        return helm_plugin_manager.get_installed_plugins()

    def install_plugins(self, cluster_id: str, plug_to_install_list: K8sPluginsToInstall):
        """
        Install a plugin to a target k8s cluster

        Args:
            cluster_id: The target k8s cluster

            plug_to_install_list: The list of enabled plugins to be installed together with data to fill plugin file
            templates.
        """
        # Getting k8s cluster from topology
        cluster = self._topology_manager.get_k8s_cluster_by_id(cluster_id)

        lb_pool: K8sLoadBalancerPoolArea = plug_to_install_list.load_balancer_pool
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)
        pod_network_cidr = get_k8s_cidr_info(k8s_config)

        # Create additional data for plugins (lbpool and cidr)
        template_fill_data = K8sPluginAdditionalData(areas=[lb_pool], pod_network_cidr=pod_network_cidr)

        helm_plugin_manager = HelmPluginManager(cluster.credentials, cluster_id)
        helm_plugin_manager.install_plugins(plug_to_install_list.plugin_list, template_fill_data)

        self.logger.success(f"Plugins {plug_to_install_list.plugin_list} have been installed")

    def apply_to_k8s(self, cluster_id: str, body):
        """
        Apply a yaml to a k8s cluster. It is like 'kubectl apply -f file.yaml'

        Args:
            cluster_id: The target cluster
            body: The yaml content to be applied at the cluster.
        """
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        # Loading a yaml in this way result in a dictionary
        dict_request = yaml.load_all(body)

        try:
            # The dictionary can be composed of multiple documents (divided by --- in the yaml)
            for document in dict_request:
                result = apply_def_to_cluster(kube_client_config=k8s_config, dict_to_be_applied=document)
        except FailToCreateError as err:
            self.logger.error(err)
            if err.args[0][0].status == 409:
                msg_err = "At least one of the yaml resources already exist"
            else:
                msg_err = err
            raise ValueError(msg_err)
        # Element in position zero because apply_def_to_cluster is working on dictionary, please look at the source
        # code of apply_def_to_cluster
        list_to_ret: List[dict] = []
        for element in result[0]:
            list_to_ret.append(element.to_dict())

        self.logger.success("Successfully applied to cluster. Created resources are: \n {}".format(list_to_ret))

    def get_k8s_cidr(self, cluster_id: str) -> dict:
        """
        Return the pod network CIDR.

        Args:

            cluster_id: the k8s cluster ID from witch the CIDR is obtained

        Returns:

            a dict {"cidr": "x.y.z.k/z"} containing the cidr of the pod network.
        """

        # Get k8s cluster and k8s config for client
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            cidr_info = get_k8s_cidr_info(k8s_config)

        except ValueError as val_err:
            self.logger.error(val_err)
            raise val_err

        return {"cidr": cidr_info}

    def get_k8s_pods(self, cluster_id: str, namespace: str = "") -> dict:
        """
        Return pods from the desired cluster, filtered by namespace

        Args:

            cluster_id: the k8s cluster ID from which the pods are obtained

            namespace: the namespace of pods to be retrieved if empty pods are retrieved for all namespaces

        Returns:

            a V1PodList list with pod belonging to the specified namespace
        """

        # Get k8s cluster and k8s config for client
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            pod_list: V1PodList = get_pods_for_k8s_namespace(kube_client_config=k8s_config, namespace=namespace)

        except ValueError as val_err:
            self.logger.error(val_err)
            raise val_err

        return pod_list.to_dict()

    # TODO doesn't work because of labels
    def create_k8s_namespace(self, cluster_id: str, name: str, labels: dict) -> OssCompliantResponse:
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            # Try to install plugins to cluster
            created_namespace: V1Namespace = k8s_create_namespace(k8s_config, namespace_name=name, labels=labels)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err, exc_info=val_err)
            return OssCompliantResponse(status=OssStatus.failed, detail=str(val_err), result={})

        return OssCompliantResponse(status=OssStatus.ready, detail="Namespace created", result=created_namespace.to_dict())

    def delete_k8s_namespace(self, cluster_id: str, name: str = "") -> OssCompliantResponse:
        """
        Delete a namespace in the target k8s cluster.

        Args:

            cluster_id: the k8s cluster ID on witch the namespace is deleted

            name: the name of the namespace to be deleted

        Returns:
            the created namespace
        """

        # Get k8s cluster and k8s config for client
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            # Try to install plugins to cluster
            created_namespace: V1Namespace = k8s_delete_namespace(k8s_config, namespace_name=name)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            resp = OssCompliantResponse(status=OssStatus.failed, detail=str(val_err), result={})
            return resp

        resp = OssCompliantResponse(status=OssStatus.ready, detail="Namespace deleted", result=created_namespace.to_dict())
        return resp

    def get_k8s_service_account(self, cluster_id: str, username: str = "", namespace: str = "") -> dict:
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            # Retrieving service account list filtered by username and namespace
            user_accounts: V1ServiceAccountList = get_service_accounts(kube_client_config=k8s_config, username=username,
                                                                       namespace=namespace)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            resp = OssCompliantResponse(status=OssStatus.failed, detail=str(val_err), result={})
            return resp

        return user_accounts.to_dict()

    def get_k8s_roles(self, cluster_id: str, rolename: str = "", namespace: str = "") -> dict:
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            # Retrieving service account list filtered by username and namespace
            role_list: V1ClusterRoleList = k8s_get_roles(kube_client_config=k8s_config, rolename=rolename,
                                                         namespace=namespace)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            resp = OssCompliantResponse(status=OssStatus.failed, detail=str(val_err), result={})
            return resp

        return role_list.to_dict()

    def get_k8s_namespace_list(self, cluster_id: str, namespace: str = "") -> dict:
        """
        Returns a list of namespaces

        Args:
            cluster_id: The cluster in which the function looks for namespaces

            namespace: the name to use as filter

        Returns:
            A namespace list (V1NamespaceList)
        """

        # Get k8s cluster and k8s config for client
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            namespace_list: V1NamespaceList = get_k8s_namespaces(kube_client_config=k8s_config, namespace=namespace)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise val_err

        return namespace_list.to_dict()


    def give_admin_rights_to_sa(self, cluster_id: str, namespace: str, s_account: str, role_binding_name: str):
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            # Retrieving service account list filtered by username and namespace
            role_bind_res: V1RoleBinding = k8s_admin_role_to_sa(kube_client_config=k8s_config, namespace=namespace,
                                                                username=s_account, role_binding_name=role_binding_name)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise val_err

        return role_bind_res.to_dict()


    def give_admin_rights_to_user_namespaced(self, cluster_id: str, namespace: str, user: str, role_binding_name: str):
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            # Retrieving service account list filtered by username and namespace
            role_bind_res: V1RoleBinding = k8s_admin_role_over_namespace(kube_client_config=k8s_config, namespace=namespace,
                                                                         username=user, role_binding_name=role_binding_name)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise val_err

        return role_bind_res.to_dict()

    def give_cluster_admin_rights(self, cluster_id: str, user: str, cluster_role_binding_name: str):
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            role_bind_res: V1ClusterRoleBinding = k8s_cluster_admin(kube_client_config=k8s_config, username=user, role_binding_name=cluster_role_binding_name)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise val_err

        return role_bind_res.to_dict()

    def create_service_account(self, cluster_id: str, namespace: str, user: str) -> dict:
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            # Creating service account
            user_creation_res: V1ServiceAccount = k8s_create_service_account(kube_client_config=k8s_config, namespace=namespace,
                                                                             username=user)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise val_err

        return user_creation_res.to_dict()

    def create_secret_for_sa(self, cluster_id: str, namespace: str, user: str, secret_name: str) -> dict:
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            # Retrieving service account list filtered by username and namespace
            created_secret: V1Secret = k8s_create_secret_for_user(kube_client_config=k8s_config,
                                                                  namespace=namespace, username=user,
                                                                  secret_name=secret_name)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise val_err

        return created_secret.to_dict()

    def get_secrets(self, cluster_id: str, namespace: str = "", secret_name: str = "", owner: str = ""):
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            auth_response: V1SecretList = k8s_get_secrets(kube_client_config=k8s_config,
                                                          namespace=namespace, secret_name=secret_name, owner=owner)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise val_err

        return auth_response.to_dict()

    def create_admin_sa_for_namespace(self, cluster_id: str, namespace: str, username: str):
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
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
            self.logger.error(val_err)
            raise val_err

        return result

    def create_k8s_kubectl_user(self, cluster_id: str, username: str, expire_seconds: int = 31536000):
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            auth_response: dict = k8s_cert_sign_req(kube_client_config=k8s_config, username=username,
                                                    expiration_sec=expire_seconds)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise val_err

        return auth_response

    def apply_resource_quota_namespace(self, cluster_id: str, namespace: str, quota_name: str, quota: K8sQuota) -> OssCompliantResponse:
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            quota_resp: V1ResourceQuota = k8s_add_quota_to_namespace(kube_client_config=k8s_config, namespace_name=namespace,
                                                                     quota_name=quota_name, quota=quota)

        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            resp = OssCompliantResponse(status=OssStatus.failed, detail=val_err.body, result={})
            return resp

        resp = OssCompliantResponse(status=OssStatus.ready, detail="Quota created", result=quota_resp.to_dict())
        return resp

    def get_nodes(self, cluster_id: str, detailed: bool = False):
        """
        Returns a list of nodes belonging to a k8s cluster

        Args:

            cluster_id:  The K8s cluster (from the topology) on witch nodes resides

            detailed: If true, a list with only names is retrieved, otherwise a V1PodList in dict form is retrieved.

        Returns:
            If detailed a list with only names is retrieved, otherwise a V1PodList in dict form is retrieved.
        """
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)
        if detailed:
            node_list: V1NodeList = k8s_get_nodes(k8s_config, detailed=detailed)
            to_return = node_list.to_dict()
        else:
            name_list = k8s_get_nodes(k8s_config, detailed=detailed)
            to_return = {"nodes": name_list}
        return to_return

    def add_label_to_k8s_node(self, cluster_id: str, node_name: str, labels: Labels):
        """
        Add labels to a k8s node

        Args:

            cluster_id: The K8s cluster (from the topology) on witch the node resides

            node_name: the name of the node on witch labels is applied

            labels: The labels to be applied

        Returns:
            The updated node V1Node in dict form
        """
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)
        node: V1Node = k8s_add_label_to_k8s_node(k8s_config, node_name=node_name, labels=labels)
        return node.to_dict()

    def get_deployment(self, cluster_id: str, namespace: str, detailed: bool = False):
        """
        Returns a list of deployments belonging to a k8s cluster

        Args:

            cluster_id: The K8s cluster (from the topology) on witch deployments resides

            namespace: The namespace in which the deployment resides

            detailed: If true, a list with only names is retrieved, otherwise a V1DeploymentList in dict form is retrieved.

        Returns:
            If detailed a list with only names is retrieved, otherwise a V1PodList in dict form is retrieved.
        """
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)
        if detailed:
            deployment_list: V1DeploymentList = k8s_get_deployments(k8s_config, namespace=namespace, detailed=detailed)
            to_return = deployment_list.to_dict()
        else:
            name_list = k8s_get_deployments(k8s_config, namespace=namespace, detailed=detailed)
            to_return = {"deployments": name_list}
        return to_return

    def add_label_to_k8s_deployment(self, cluster_id: str, namespace: str, deployment_name: str, labels: Labels):
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)
        deployment: V1Deployment = k8s_add_label_to_k8s_deployment(k8s_config, namespace=namespace, deployment_name=deployment_name, labels=labels)
        return deployment.to_dict()

    def scale_k8s_deployment(self, cluster_id: str, namespace: str, deployment_name: str, replica_number: int):
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
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)
        deployment: V1Deployment = k8s_scale_k8s_deployment(k8s_config, namespace=namespace, deployment_name=deployment_name, replica_num=replica_number)
        return deployment.to_dict()

    def get_k8s_ipaddress_pools(self, cluster_id: str) -> List[str]:
        """
        Retrieve a list of IP addresses pools in the cluster used by the Load Balancer.

        Returns:

            A list of IP address pools. If there is no pool, an empty list is returned. This means that the LB has not been configured
        """
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)
        ip_pool_list = k8s_get_ipaddress_pool(k8s_config)
        return ip_pool_list

    def get_k8s_storage_classes(self, cluster_id: str) -> List[str]:
        """
        Retrieve a list of storage classes in the cluster
        Args:

            cluster_id: The cluster id

        Returns:

            A list of storage classes
        """
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)
        storage_classes = k8s_get_storage_classes(k8s_config)
        sc_name_list = []
        for sc in storage_classes.items:
            sc_name_list.append(sc.metadata.name)
        return sc_name_list

    def get_k8s_default_storage_class(self, cluster_id: str) -> str | None:
        """
        Retrieve the default storage class in the cluster
        Args:

            cluster_id: The cluster id

        Returns:

            The default storage class, empty if none
        """
        cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)
        storage_classes = k8s_get_storage_classes(k8s_config)
        for sc in storage_classes.items:
            if sc.metadata.annotations.get("storageclass.kubernetes.io/is-default-class") == "true":
                return sc.metadata.name
        return None
