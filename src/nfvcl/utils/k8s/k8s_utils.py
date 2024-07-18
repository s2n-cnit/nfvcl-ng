import tempfile
import time
import traceback
from logging import Logger
from typing import List

import kubernetes.client
import kubernetes.utils
import yaml
from kubernetes import config
from kubernetes.client import Configuration, V1PodList, V1DaemonSetList, VersionInfo, V1ConfigMap, \
    V1Namespace, V1ObjectMeta, V1ServiceList, V1DeploymentList
from kubernetes.client.rest import ApiException
from kubernetes.utils import FailToCreateError

import nfvcl.utils.util
from nfvcl.config_templates.k8s.k8s_plugin_config_manager import get_yaml_files_for_plugin, get_enabled_plugins
from nfvcl.models.k8s.plugin_k8s_model import K8sTemplateFillData, K8sPluginName, K8sPluginType
from nfvcl.models.k8s.topology_k8s_model import K8sModel, K8sVersion
from nfvcl.utils.k8s.k8s_client_extension import create_from_yaml_custom
from nfvcl.utils.log import create_logger

TIMEOUT_SECONDS = 10
logger: Logger = create_logger("K8S UTILS")


# TODO split this file: API method goes in a dedicated file


class check_k8s_version(object):
    """
    This is a DECORATOR. Allow to decorate a method to require a minimum version of k8s cluster
    The decorated method (or function) **must** have as first parameter the kubernetes.client.Configuration for building the k8s
    client.

    Raises:
        ValueError if the decorator is used on not compatible method or if the k8s version is too low for it.
    """

    def __init__(self, min_version: K8sVersion):
        """
        Args:
            min_version: the minimum version required
        """
        # this is actually needed in the complete code
        self.min_version: K8sVersion = min_version

    def __call__(self, func):
        """
        This method is called when the decorated method is called.
        """

        def wrapped_f(*args, **kwargs):
            if len(args) > 0:
                if isinstance(args[0], kubernetes.client.Configuration):
                    target_config: kubernetes.client.Configuration = args[0]
                    actual_version = get_k8s_version(target_config)
                    if not actual_version.is_minor(self.min_version):
                        return func(*args, **kwargs)
                    else:
                        msg_err = "The version of k8s cluster is too low. Requested APIs for this method are not" \
                                  "implemented."
                        logger.error(msg_err)
                        raise ValueError(msg_err)

            # In any unforeseen case, throw error.
            msg_err = "The decorator has been used on incompatible method, first argument must be instance " \
                      "of kubernetes.client.Configuration"
            logger.error(msg_err)
            raise ValueError(msg_err)

        return wrapped_f


def get_k8s_config_from_file_content(kube_client_config_file_content: str) -> kubernetes.client.Configuration:
    """
    Create a kube client config from the content of configuration file. It creates a temp file and read it's content in
    order to create the k8s config
    @param kube_client_config_file_content: the content of the configuration file

    @return kube client configuration
    """
    tmp = tempfile.NamedTemporaryFile()
    try:
        with open(tmp.name, 'w') as f:
            f.write(kube_client_config_file_content)
        tmp.flush()

        kube_client_config = type.__call__(Configuration)
        config.load_kube_config(config_file=tmp.name, context=None, client_configuration=kube_client_config,
                                persist_config=False)
        kube_client_config.verify_ssl = False
    finally:
        tmp.close()

    return kube_client_config


def get_config_for_k8s_from_dict(kube_client_config_dict: dict) -> kubernetes.client.Configuration:
    """
    Create a kube client config from dictionary.
    @param kube_client_config_dict: the dictionary that contains configuration parameters

    @return kube client configuration
    """
    kube_client_config = type.__call__(Configuration)
    config.load_kube_config_from_dict(config_file=kube_client_config_dict, context=None,
                                      client_configuration=kube_client_config,
                                      persist_config=False)
    kube_client_config.verify_ssl = False

    return kube_client_config


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


def get_installed_plugins(kube_client_config: kubernetes.client.Configuration) -> List[K8sPluginName]:
    """
    Check which plugin is installed on a k8s cluster. To this goal, daemon sets and pods in 'kube system' are iterated.
    The function check if there are labels that highlight the presence of a plugin.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.

    Returns
        the list of detected plugins in a k8s cluster
    """
    enabled_plugins = get_enabled_plugins()
    to_return = []

    # Not the efficient way but this function should be called rarely
    for plugin in enabled_plugins:
        # For each plugin that is detected by the presence of a daemon set
        for daemon_set in plugin.daemon_sets:
            label = f"{daemon_set.label}={daemon_set.value}"
            retrieved_daemons = get_daemon_sets(kube_client_config, namespace=daemon_set.namespace, label_selector=label)
            if len(retrieved_daemons.items) > 0:
                to_return.append(K8sPluginName(plugin.name))

        # For each plugin that is detected by the presence of a deployment
        for deploy in plugin.deployments:
            label = f"{deploy.label}={deploy.value}"
            retrieved_daemons = get_daemon_sets(kube_client_config, namespace=deploy.namespace, label_selector=label)
            if len(retrieved_daemons.items) > 0:
                to_return.append(K8sPluginName(plugin.name))

    return to_return


def patch_config_map(kube_client_config: kubernetes.client.Configuration, name, namespace, config_map: V1ConfigMap):
    """
        Patch a config map in a k8s cluster.

        Args:
            kube_client_config: the configuration of K8s on which the client is built.
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
                         yaml_file_to_be_applied: str = None):
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
                result_yaml = create_from_yaml_custom(api_client, yaml_file_to_be_applied)
        except ApiException as error:
            logger.error("Exception when calling create_from_yaml: {}\n".format(error))
            raise error
        finally:
            api_client.close()
    return result_dict, result_yaml


def install_plugins_to_cluster(kube_client_config: kubernetes.client.Configuration,
                               plugins_to_install: List[K8sPluginName],
                               template_fill_data: K8sTemplateFillData,
                               cluster_id: str,
                               skip_plug_checks: bool = False) -> dict:
    """
    Install a plugin list at the target k8s cluster.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.

        plugins_to_install: List[K8sPluginName] the list of plugins to install on the cluster.

        template_fill_data: data to fill plugins yaml file templates. If additional_data.pod_network_cidr is null,
        the function is retrieving this value from k8s cluster.

        cluster_id: The ID of the k8s cluster, used to give a name to configuration files

        skip_plug_checks: skip plugin checks (already installed...)

    Returns:
        A dict[List[List[K8sTypes]]]: for each plugin a new key for the dictionary is created witch contains a list of resource types
        (V1Pod, V1DaemonSet, ...) and for each resource type there is a list of elements.

    Raises:
        ValueError if some plugins are already installed or there is a conflict
    """
    version: K8sVersion = get_k8s_version(kube_client_config)

    installed_plugins: List[K8sPluginName] = get_installed_plugins(kube_client_config)

    result: dict = {}

    # Checking plugins to be installed, that ones to be installed are not already present.
    # Raise error if problem
    if not skip_plug_checks:
        check_plugin_to_be_installed(installed_plugins=installed_plugins, plugins_to_install=plugins_to_install)

    for plugin in plugins_to_install:
        # Yaml files to be applied to the cluster for each plugin
        yaml_file_configs_templates = get_yaml_files_for_plugin(version, plugin)

        rendered_files_list = nfvcl.utils.util.render_files_from_template(paths=yaml_file_configs_templates,
                                                                          render_dict=template_fill_data.model_dump(),
                                                                          files_name_prefix=cluster_id)

        result_list = []
        logger.info("Plugin <{}> installation is starting.".format(plugin.name))
        for yaml_file in rendered_files_list:
            # Element in position 1 because apply_def_to_cluster is working on yaml file, please look at the source
            # code of apply_def_to_cluster
            try:
                result_list.append(apply_def_to_cluster(kube_client_config, yaml_file_to_be_applied=yaml_file)[1])
            except FailToCreateError as fail:
                logger.warning(traceback.format_tb(fail.__traceback__))
                logger.warning("Definition <{}> for plugin <{}> has gone wrong. Retrying in 60 seconds...".
                               format(yaml_file, plugin.name))
                time.sleep(60)
                result_list.append(apply_def_to_cluster(kube_client_config, yaml_file_to_be_applied=yaml_file)[1])

            # If it is the last does not wait
            if not rendered_files_list[-1] == yaml_file:
                logger.info(
                    "Yaml definition ({}/{}) for {} have been applied. Waiting 30 seconds before next definition.".
                    format(len(result_list), len(rendered_files_list), plugin.name))
                time.sleep(30)
        result[plugin.value] = result_list

        # If it is the last plugin it does NOT wait
        if not plugins_to_install[-1] == plugin:
            logger.info(
                "Plugin <{}> definitions have been applied. Waiting 30 seconds before next plugin.".format(plugin.name))
            time.sleep(30)
    return result


def k8s_create_namespace(kube_client_config: kubernetes.client.Configuration, namespace_name: str,
                         labels: dict) -> V1Namespace:
    """
    Create a namespace in a k8s cluster.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        namespace_name: The name of the namespace
        labels: K8s labels to be applied at the namespace.

    Returns:
        The created namespace
    """
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the API class
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        object_metadata = V1ObjectMeta(name=namespace_name, labels=labels)
        namespace: V1Namespace = V1Namespace(api_version='v1', kind='Namespace', metadata=object_metadata)
        try:
            namespace = api_instance_core.create_namespace(body=namespace)
        except ApiException as error:
            logger.error("Exception when calling CoreV1Api>create_namespace: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return namespace


def check_plugin_to_be_installed(installed_plugins: List[K8sPluginName], plugins_to_install: List[K8sPluginName]):
    """
    Checks that plugins are in enabled list.
    Next it check that ones to be installed are not already present.
    Finally, that there is no conflict between them.

    Args:
        installed_plugins: list of installed plugins

        plugins_to_install: list of plugins to be installed

    Raises:
        ValueError if:
            - Plugins are already present in the cluster
            - There is a conflict between installed plugins + ones to be installed (same type of plugin)

    """

    # Checking if plugins to be installed have element in common with installed plugins
    common_elements = list(set(installed_plugins).intersection(plugins_to_install))
    if len(common_elements) > 0:
        msg_err = "Plugins {} are already present in the cluster.".format(common_elements)
        raise ValueError(msg_err)

    types: List[str] = []
    union = set(installed_plugins).union(plugins_to_install)
    # Getting enabled plugins list of the union (installed+to be installed).
    filtered_enabled_plugins = get_enabled_plugins(union)

    # Create a list for k8s plugin types, in order to check if there are conflicts.
    types: List[K8sPluginType] = []
    for plugin in filtered_enabled_plugins:
        plugin_type = K8sPluginType(plugin.type)
        # If type is already present -> Conflict
        # If type is generic -> No need to check for conflict
        if plugin_type in types and plugin_type is not K8sPluginType.GENERIC:
            msg_warning = "There is a conflict between installed plugins + ones to be installed. 2 or more plugins of " \
                          "the same type {} have been found (Example calico and flannel)".format(plugin_type)
            logger.warning(msg_warning)
        types.append(plugin_type)


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
            config_map: V1ConfigMap = core_v1_api.read_namespaced_config_map(name=config_name,
                                                                             namespace=namespace)
        except ApiException as error:
            logger.error("Exception when calling ApisApi->get_api_versions: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return config_map


def parse_k8s_clusters_from_dict(k8s_list: List[dict]) -> List[K8sModel]:
    """
    From a k8s cluster list in dictionary form returns a list of corresponding k8s models.

    Args:
        k8s_list: dict to convert into K8sModel objects

    Returns:

        a list of K8sModel objects
    """
    k8s_obj_list: List[K8sModel] = []
    for k8s in k8s_list:
        k8s_object = K8sModel.model_validate(k8s)
        k8s_obj_list.append(k8s_object)
    return k8s_obj_list


def find_k8s_from_list_by_id(cluster_list: List[K8sModel], cluster_id: str) -> K8sModel:
    """
    Get the k8s corresponding cluster from the list.

    Args:

        cluster_list: the list in which the method search the corresponding cluster

        cluster_id: the cluster ID that identify a k8s cluster in the list.

    Returns:

        The matching k8s cluster or Throw ValueError if NOT found.
    """
    try:
        match = next((x for x in cluster_list if x.name == cluster_id), None)

        if match:
            return match
        else:
            msg_err = "The k8s cluster {} has not been found in the topology".format(cluster_id)
            raise ValueError(msg_err)
    except Exception as err:
        logger.error(err)
        raise err


def convert_str_list_2_plug_name(list_to_convert: List[str]) -> List[K8sPluginName]:
    """
    Convert a list of string into a list of K8sPluginName.

    Args:
        list_to_convert: the list of string to be converted.

    Returns:
        the converted List[K8sPluginName]

    Raises:
        ValueError if one or more strings are not valid K8sPluginNames.
    """
    to_return: List[K8sPluginName] = []
    for str in list_to_convert:
        try:
            to_return.append(K8sPluginName(str))
        except ValueError as e:
            logger.error("Error in conversion from {} to K8sPluginName. This is not a valid enum value.".format(str))
            raise e
    return to_return
