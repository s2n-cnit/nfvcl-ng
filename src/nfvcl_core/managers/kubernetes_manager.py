from time import sleep
from typing import List

from kubernetes.client import V1PodList, V1Namespace, ApiException, V1ServiceAccountList, V1NamespaceList, \
    V1RoleBinding, V1ClusterRoleBinding, V1ServiceAccount, V1Secret, V1SecretList, V1ResourceQuota, V1NodeList, V1Node, \
    V1DeploymentList, V1Deployment, V1RoleList
from kubernetes.utils import FailToCreateError

from nfvcl_core.managers import TopologyManager, BlueprintManager, EventManager
from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core.utils.blue_utils import yaml
from nfvcl_core.utils.k8s.helm_plugin_manager import HelmPluginManager
from nfvcl_core.utils.k8s.k8s_utils import get_k8s_config_from_file_content
from nfvcl_core.utils.k8s.kube_api_utils_class import KubeApiUtils
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.k8s_management_models import Labels
from nfvcl_core_models.plugin_k8s_model import K8sPluginName, K8sPluginsToInstall, K8sLoadBalancerPoolArea, \
    K8sPluginAdditionalData, K8sMonitoringConfig
from nfvcl_core_models.response_model import OssCompliantResponse, OssStatus
from nfvcl_core_models.topology_k8s_model import TopologyK8sModel, K8sQuota


class KubernetesManager(GenericManager):
    def __init__(self, topology_manager: TopologyManager, blueprint_manager: BlueprintManager, event_manager: EventManager):
        super().__init__()
        self._topology_manager = topology_manager
        self._blueprint_manager = blueprint_manager
        self._event_manager = event_manager
        self._k8s_api_utils_cache = {}

    def get_k8s_api_utils(self, cluster_id: str) -> KubeApiUtils:
        """
        Get a KubeApiUtils instance for the specified cluster.

        Args:
            cluster_id: The ID of the Kubernetes cluster.

        Returns:
            An instance of KubeApiUtils for the specified cluster.
        """
        if cluster_id not in self._k8s_api_utils_cache:
            cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
            k8s_config = get_k8s_config_from_file_content(cluster.credentials)
            self._k8s_api_utils_cache[cluster_id] = KubeApiUtils(kube_client_config=k8s_config)

        return self._k8s_api_utils_cache[cluster_id]

    def get_k8s_installed_plugins(self, cluster_id: str) -> List[K8sPluginName]:
        """
        Return installed plugins on a cluster

        Args:

            cluster_id: [str] the cluster id

        Returns:

            A list of installed plugins
        """
        try:
            cluster: TopologyK8sModel = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
            helm_plugin_manager = HelmPluginManager(cluster.credentials, "K8S REST UTILS")
            return helm_plugin_manager.get_installed_plugins()
        except ValueError as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=404)

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
        k8s_api = self.get_k8s_api_utils(cluster_id)
        pod_network_cidr = k8s_api.get_cidr_info()

        # Create additional data for plugins (lbpool and cidr)
        template_fill_data = K8sPluginAdditionalData(areas=[lb_pool] if lb_pool else None, pod_network_cidr=pod_network_cidr)

        helm_plugin_manager = HelmPluginManager(cluster.credentials, cluster_id)
        helm_plugin_manager.install_plugins(plug_to_install_list.plugin_list, template_fill_data)

        self.logger.success(f"Plugins {plug_to_install_list.plugin_list} have been installed")

    def retrieve_monitoring_data(self, cluster_id: str, loki_id: str, prometheus_id: str):
        """

        Args:
            cluster_id: from the topology
            loki_id: from the topology
            prometheus_id: from the topology

        Returns: cluster, loki, prometheus from topology if there exist otherwise None for each one

        """
        try:
            cluster = self._topology_manager.get_k8s_cluster_by_id(cluster_id)
        except NFVCLCoreException:
            cluster = None
        try:
            loki = self._topology_manager.get_loki(loki_id)
        except NFVCLCoreException:
            loki = None
        try:
            prometheus = self._topology_manager.get_prometheus(prometheus_id)
        except NFVCLCoreException:
            prometheus = None
        return cluster, loki, prometheus

    def install_k8s_monitoring(self, cluster_id: str, config: K8sMonitoringConfig):
        """
        Install k8s-monitoring to a target k8s cluster

        Args:
            cluster_id: The target k8s cluster


            config: K8sMonitoring configuration data
        """
        metrics = self._topology_manager.get_k8s_cluster_monitoring_metrics_config(cluster_id)
        if metrics:
            self.logger.warning(f"K8sMonitoring already installed in cluster {cluster_id}")
        else:
            cluster, loki, prometheus = self.retrieve_monitoring_data(cluster_id, config.loki_id, config.prometheus_id)
            if cluster and (loki or prometheus):
                template_fill_data = K8sPluginAdditionalData(loki=loki, prometheus=prometheus, k8smonitoring_node_exporter_enabled=config.node_exporter_enabled, k8smonitoring_node_exporter_label=config.node_exporter_label)
                helm_plugin_manager = HelmPluginManager(cluster.credentials, cluster_id)
                config = helm_plugin_manager.install_k8s_monitoring(template_fill_data)
                self._topology_manager.add_edit_k8s_cluster_monitoring_metrics(cluster_id, config)
                self.logger.success(f"Plugins {[K8sPluginName.K8S_MONITORING]} have been installed")
            else:
                self.logger.warning(f"Cluster retrieved is {cluster.name if cluster else None}, Loki is {loki.id if loki else None}, Prometheus is {prometheus.id if prometheus else None}")

    def add_monitoring_destination(self, cluster_id: str, loki_id: str, prometheus_id: str):
        """

        Args:
            cluster_id: where k8-monitoring running
            loki_id:
            prometheus_id:

        """
        metrics = self._topology_manager.get_k8s_cluster_monitoring_metrics_config(cluster_id)
        tmp = metrics.__deepcopy__()
        if metrics:
            cluster, loki, prometheus = self.retrieve_monitoring_data(cluster_id, loki_id, prometheus_id)
            if cluster and (loki or prometheus):
                template_fill_data = K8sPluginAdditionalData(loki=loki, prometheus=prometheus, k8smonitoring_config=metrics)
                helm_plugin_manager = HelmPluginManager(cluster.credentials, cluster_id)
                config = helm_plugin_manager.add_metrics_destination(template_fill_data)
                if config == tmp:
                    self.logger.warning("Destination already exits")
                    return
                self._topology_manager.add_edit_k8s_cluster_monitoring_metrics(cluster_id, config)
                self.logger.success(f"Plugins {[K8sPluginName.K8S_MONITORING]} have been updated")
            else:
                self.logger.warning(f"Cluster retrieved is {cluster.name if cluster else None}, Loki is {loki.id if loki else None}, Prometheus is {prometheus.id if prometheus else None}")
        else:
            self.logger.warning(f"K8sMonitoring is not installed in cluster {cluster_id}")

    def del_monitoring_destination(self, cluster_id: str, loki_id: str, prometheus_id: str):
        """

        Args:
            cluster_id:
            loki_id:
            prometheus_id:

        Returns:

        """
        metrics = self._topology_manager.get_k8s_cluster_monitoring_metrics_config(cluster_id)
        if metrics:
            if len(metrics.destinations) <= 1:
                self.logger.warning(f"At least one monitoring destination is needed, uninstall the plugin if you want to remove it")
                return
            cluster, loki, prometheus = self.retrieve_monitoring_data(cluster_id, loki_id, prometheus_id)
            if cluster and (loki or prometheus):
                template_fill_data = K8sPluginAdditionalData(loki=loki, prometheus=prometheus, k8smonitoring_config=metrics)
                helm_plugin_manager = HelmPluginManager(cluster.credentials, cluster_id)
                config = helm_plugin_manager.del_metrics_destination(template_fill_data)
                if config == metrics:
                    self.logger.warning("Destination not exits")
                    return
                self._topology_manager.add_edit_k8s_cluster_monitoring_metrics(cluster_id, config)
                self.logger.success(f"Plugins {[K8sPluginName.K8S_MONITORING]} have been updated")
            else:
                self.logger.warning(f"Cluster retrieved is {cluster.name if cluster else None}, Loki is {loki.id if loki else None}, Prometheus is {prometheus.id if prometheus else None}")
        else:
            self.logger.warning(f"K8sMonitoring is not installed in cluster {cluster_id}")

    def uninstall_plugin(self, cluster_id: str, namespace: str, wait=True):
        """
        Uninstall a plugin to a target k8s cluster

        Args:
            wait: for task to finish
            cluster_id: The target k8s cluster
            namespace: Namespace to be uninstalled
        """
        cluster = self._topology_manager.get_k8s_cluster_by_id(cluster_id)

        helm_plugin_manager = HelmPluginManager(cluster.credentials, cluster_id)
        helm_plugin_manager.uninstall_plugin(namespace.lower(), wait=wait)
        self.logger.success(f"Plugin at namespace {namespace.lower()} have been uninstalled")

    def uninstall_k8s_monitoring(self, cluster_id: str):
        """
        Uninstall a plugin to a target k8s cluster

        Args:
            cluster_id: The target k8s cluster
        """
        metrics = self._topology_manager.get_k8s_cluster_monitoring_metrics_config(cluster_id)
        if metrics:
            namespace = "alloy-metrics"
            self.uninstall_plugin(cluster_id, namespace, wait=False)
            k8s = self.get_k8s_api_utils(cluster_id)
            k8s.remove_alloy_finalizier(namespace)
            k8s.delete_namespace(namespace)
            not_deleted = True
            while not_deleted:
                namespaces = k8s.get_namespaces(namespace)
                if len(namespaces.items) == 0:
                    not_deleted = False
                self.logger.info(f"Waiting namespace {namespace} have been deleted")
                sleep(5)
            self._topology_manager.delete_k8s_cluster_monitoring_metrics(cluster_id)
            self.logger.success(f"K8sMonitoring successfully uninstalled")
        else:
            self.logger.warning(f"K8sMonitoring is not installed in cluster {cluster_id}")

    def apply_to_k8s(self, cluster_id: str, body):
        """
        Apply a yaml to a k8s cluster. It is like 'kubectl apply -f file.yaml'

        Args:
            cluster_id: The target cluster
            body: The yaml content to be applied at the cluster.
        """
        # Loading a yaml in this way result in a dictionary
        dict_request = yaml.load_all(body)

        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            list_to_ret: List[dict] = []

            # The dictionary can be composed of multiple documents (divided by --- in the yaml)
            for document in dict_request:
                result = k8s_api.apply_def_to_cluster(dict_to_be_applied=document)
                for element in result:
                    list_to_ret.append(element.to_dict())

        except FailToCreateError as err:
            self.logger.error(err)
            if err.args[0][0].status == 409:
                msg_err = "At least one of the yaml resources already exist"
            else:
                msg_err = err
            raise ValueError(msg_err)

        self.logger.success("Successfully applied to cluster. Created resources are: \n {}".format(list_to_ret))

    def get_k8s_cidr(self, cluster_id: str) -> dict:
        """
        Return the pod network CIDR.

        Args:

            cluster_id: the k8s cluster ID from witch the CIDR is obtained

        Returns:

            a dict {"cidr": "x.y.z.k/z"} containing the cidr of the pod network.
        """
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            cidr_info = k8s_api.get_cidr_info()
        except ApiException as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            pod_list: V1PodList = k8s_api.get_pods_for_namespace(namespace=namespace)
        except ApiException as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            created_namespace: V1Namespace = k8s_api.create_namespace(namespace_name=name, labels=labels)
        except ApiException as val_err:
            self.logger.error(val_err, exc_info=val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            deleted_namespace: V1Namespace = k8s_api.delete_namespace(namespace_name=name)
        except ApiException as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

        resp = OssCompliantResponse(status=OssStatus.ready, detail="Namespace deleted", result=deleted_namespace.to_dict())
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
            k8s_api = self.get_k8s_api_utils(cluster_id)
            user_accounts: V1ServiceAccountList = k8s_api.get_service_accounts(namespace=namespace, username=username)
        except ApiException as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

        return user_accounts.to_dict()

    def get_k8s_roles(self, cluster_id: str, rolename: str = "", namespace: str = "") -> V1RoleList:
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
            k8s_api = self.get_k8s_api_utils(cluster_id)
            role_list: V1RoleList = k8s_api.get_roles(rolename=rolename, namespace=namespace)
            if len(role_list.items) == 0:
                raise NFVCLCoreException("No role found", http_equivalent_code=404)
        except (ApiException, ValueError) as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

        return role_list

    def get_k8s_namespace_list(self, cluster_id: str, namespace: str = "") -> dict:
        """
        Returns a list of namespaces

        Args:
            cluster_id: The cluster in which the function looks for namespaces

            namespace: the name to use as a filter

        Returns:
            A namespace list (V1NamespaceList)
        """

        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            namespace_list: V1NamespaceList = k8s_api.get_namespaces(namespace=namespace)
        except ApiException as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

        return namespace_list.to_dict()

    def give_admin_rights_to_sa(self, cluster_id: str, namespace: str, s_account: str, role_binding_name: str):
        """
        Give admin rights to an EXISTING service account (SA) in a namespace.

        Args:
            cluster_id: The target k8s cluster id

            namespace: The namespace on which the admin rights are given to the target user.

            s_account: The existing service account that will become administrator

            role_binding_name: The name that will be given to the RoleBinding

        Returns:
            The created role binding (V1RoleBinding)
        """
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            role_bind_res: V1RoleBinding = k8s_api.admin_role_to_sa(namespace=namespace, username=s_account, role_binding_name=role_binding_name)
        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

        return role_bind_res.to_dict()

    def give_cluster_admin_rights(self, cluster_id: str, s_account: str, namespace: str, cluster_role_binding_name: str):
        """
        Give cluster admin rights to a service account.

        Args:
            cluster_id: The target k8s cluster id

            s_account: The user that will become administrator for the cluster

            namespace: The namespace to which the user belongs.

            cluster_role_binding_name: The name that will be given to the ClusterRoleBinding

        Returns:
            The created role binding (V1ClusterRoleBinding)
        """
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            role_bind_res: V1ClusterRoleBinding = k8s_api.cluster_admin_to_sa(username=s_account, namespace=namespace, role_binding_name=cluster_role_binding_name)
        except ApiException as error:
            raise NFVCLCoreException(message=str(error), http_equivalent_code=error.status)
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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            user_creation_res: V1ServiceAccount = k8s_api.create_service_account(namespace=namespace, username=user)
        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

        return user_creation_res.to_dict()

    def create_admin_sa_for_namespace(self, cluster_id: str, namespace: str, username: str):
        """
        Create a Service Account with admin rights in the target namespace.

        1 - Create the user

        2 - Create the Admin Role for that namespace

        3 - Role binds the admin role to the user on the target namespace

        3 - Create a secret for the user

        4 - Return created resources

        Args:
            cluster_id: The target k8s cluster.

            namespace: The namespace in which the user is created

            username: The name of the user

        Returns:
            a dictionary containing the created resources:
            {"service_account": sa.to_dict(),
            "secret": detailed_secret.to_dict()}

        """
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            # Creating SA
            sa = k8s_api.create_service_account(namespace=namespace, username=username)
            # Creating Role
            admin_role = k8s_api.create_admin_role(namespace)
            # Creating role binding to be admin
            binding_name = "rolebinding_admin_" + username
            role_binding = k8s_api.admin_role_to_sa(namespace=namespace, username=username, role_binding_name=binding_name)
            # Create secret
            secret_name = username + "-secret"
            secret = k8s_api.create_secret_for_user(namespace=namespace, username=username, secret_name=secret_name)
            # Returning secret WITH token included
            detailed_secret = k8s_api.get_secrets(namespace=namespace, secret_name=secret.metadata.name)
            result = {
                "service_account": sa.to_dict(),
                "secret": detailed_secret.to_dict()
            }
        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)
        return result

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            created_secret: V1Secret = k8s_api.create_secret_for_user(namespace=namespace,
                                                                      username=user,
                                                                      secret_name=secret_name)
        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            auth_response: V1SecretList = k8s_api.get_secrets(
                namespace=namespace, secret_name=secret_name, owner=owner)
        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

        return auth_response.to_dict()

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            auth_response: dict = k8s_api.cert_sign_req(username=username, expiration_sec=expire_seconds)
        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            quota_resp: V1ResourceQuota = k8s_api.add_quota_to_namespace(
                namespace_name=namespace, quota_name=quota_name, quota=quota)
        except (ValueError, ApiException) as val_err:
            self.logger.error(val_err)
            resp = OssCompliantResponse(status=OssStatus.failed, detail=str(val_err), result={})
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

        resp = OssCompliantResponse(status=OssStatus.ready, detail="Quota created", result=quota_resp.to_dict())
        return resp

    def get_nodes(self, cluster_id: str, detailed: bool = False):
        """
        Returns a list of nodes belonging to a k8s cluster

        Args:

            cluster_id:  The K8s cluster (from the topology) on witch nodes resides

            detailed: If true, a V1PodList in dict form is retrieved, otherwise a list with only names is retrieved.

        Returns:
            If detailed a V1PodList in dict form is retrieved, otherwise a list with only names is retrieved.
        """
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            if detailed:
                node_list: V1NodeList = k8s_api.get_nodes(detailed=detailed)
                to_return = node_list.to_dict()
            else:
                name_list = k8s_api.get_nodes(detailed=detailed)
                to_return = {"nodes": name_list}
            return to_return
        except ApiException as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            node: V1Node = k8s_api.add_label_to_k8s_node(node_name=node_name, labels=labels)
            return node.to_dict()
        except ApiException as api_exp:
            self.logger.error(api_exp)
            raise NFVCLCoreException(message=str(api_exp), http_equivalent_code=500)

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            if detailed:
                deployment_list: V1DeploymentList = k8s_api.get_deployments(namespace=namespace, detailed=detailed)
                to_return = deployment_list.to_dict()
            else:
                name_list = k8s_api.get_deployments(namespace=namespace, detailed=detailed)
                to_return = {"deployments": name_list}
            return to_return
        except ApiException as val_err:
            self.logger.error(val_err)
            raise NFVCLCoreException(message=str(val_err), http_equivalent_code=500)

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            deployment: V1Deployment = k8s_api.add_label_to_k8s_deployment(
                namespace=namespace, deployment_name=deployment_name, labels=labels)
            return deployment.to_dict()
        except ApiException as api_exp:
            self.logger.error(api_exp)
            raise NFVCLCoreException(message=str(api_exp), http_equivalent_code=500)

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
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            deployment: V1Deployment = k8s_api.scale_k8s_deployment(
                namespace=namespace, deployment_name=deployment_name, replica_num=replica_number)
            return deployment.to_dict()
        except ApiException as api_exp:
            self.logger.error(api_exp)
            raise NFVCLCoreException(message=str(api_exp), http_equivalent_code=500)

    def get_k8s_ipaddress_pools(self, cluster_id: str) -> List[str]:
        """
        Retrieve a list of IP addresses pools in the cluster used by the Load Balancer.

        Returns:

            A list of IP address pools. If there is no pool, an empty list is returned. This means that the LB has not been configured
        """
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            ip_pool_list = k8s_api.get_ipaddress_pool()
            return ip_pool_list
        except ApiException as api_exp:
            self.logger.error(api_exp)
            raise NFVCLCoreException(message=str(api_exp), http_equivalent_code=500)

    def get_k8s_storage_classes(self, cluster_id: str) -> List[str]:
        """
        Retrieve a list of storage classes in the cluster
        Args:

            cluster_id: The cluster id

        Returns:

            A list of storage classes
        """
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            storage_classes = k8s_api.get_storage_classes()

            sc_name_list = []
            for sc in storage_classes.items:
                sc_name_list.append(sc.metadata.name)
            return sc_name_list
        except ApiException as api_exp:
            self.logger.error(api_exp)
            raise NFVCLCoreException(message=str(api_exp), http_equivalent_code=500)

    def get_k8s_default_storage_class(self, cluster_id: str) -> str | None:
        """
        Retrieve the default storage class in the cluster
        Args:

            cluster_id: The cluster id

        Returns:

            The default storage class, empty if none
        """
        try:
            k8s_api = self.get_k8s_api_utils(cluster_id)
            storage_classes = k8s_api.get_storage_classes()

            for sc in storage_classes.items:
                if sc.metadata.annotations and sc.metadata.annotations.get("storageclass.kubernetes.io/is-default-class") == "true":
                    return sc.metadata.name
            return None
        except ApiException as api_exp:
            self.logger.error(api_exp)
            raise NFVCLCoreException(message=str(api_exp), http_equivalent_code=500)

    def install_nfvcl_admission_webhook(self, cluster_id: str):
        k8s_api = self.get_k8s_api_utils(cluster_id)

        if "certificates.cert-manager.io" not in k8s_api.get_custom_resource_definitions():
            self.logger.info("Cert Manager is not installed. Installing it now...")

            self.install_plugins(cluster_id, K8sPluginsToInstall(plugin_list=[
                K8sPluginName.CERT_MANAGER
            ]))
        else:
            self.logger.info("Cert Manager is already installed. Continuing with NFVCL Admission Webhook installation...")

        self.logger.info("Installing NFVCL Admission Webhook...")
        self.install_plugins(cluster_id, K8sPluginsToInstall(plugin_list=[
            K8sPluginName.NFVCL_WEBHOOK
        ]))
        self.logger.info("NFVCL Admission Webhook installed successfully.")
        return "NFVCL Admission Webhook installed successfully."

    def uninstall_nfvcl_admission_webhook(self, cluster_id: str):
        k8s_api = self.get_k8s_api_utils(cluster_id)
        self.logger.info("Uninstalling NFVCL Admission Webhook...")
        try:
            k8s_api.delete_mutating_webhook_configuration("nfvcl-webhook")
            k8s_api.delete_namespace("nfvcl-webhook")
            self.logger.info("NFVCL Admission Webhook uninstalled successfully.")
            return "NFVCL Admission Webhook uninstalled successfully."
        except Exception as e:
            self.logger.error(f"Error uninstalling NFVCL Admission Webhook: {e}")
            raise NFVCLCoreException(message=str(e), http_equivalent_code=500)
