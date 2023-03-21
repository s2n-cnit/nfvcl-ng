import logging
import tempfile
from typing import List
import kubernetes.client
import kubernetes.utils
from kubernetes import config
from kubernetes.client import Configuration, V1PodList, V1DaemonSetList, V1DaemonSet, V1APIGroupList, VersionInfo
from kubernetes.client.rest import ApiException
from config_templates.k8s.k8s_config_manager import get_plugin_config_for_k8s_version

from models.k8s import K8sModel, K8sDaemon, K8sVersion


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


def get_pods_for_k8s_namespace(kube_client_config: kubernetes.client.Configuration, namespace: str) -> V1PodList:
    """
    Get pods from a k8s instance that belongs to the given namespace

    @param kube_client_config the configuration of K8s on which the client is built.

    @rtype V1PodList
    @return: Return the list of pods (as V1PodList) belonging to that namespace in the given k8s cluster.
    """
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the API class
        api_instance_core = kubernetes.client.CoreV1Api(api_client)
        pod_list: V1PodList = None
        try:
            pod_list = api_instance_core.list_namespaced_pod(namespace=namespace.lower())
        except ApiException as error:
            logging.error("Exception when calling CoreV1Api>list_namespaced_pod: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return pod_list


def get_daemon_sets(kube_client_config: kubernetes.client.Configuration, namespace: str = None) -> V1DaemonSetList:
    """
    Search for all DeamonSets of a namespace. If a namespace is not specified, it will work on
    all namespaces.

    @param kube_client_config the configuration of K8s on which the client is built.
    @param namespace, the optional namespace. If None the search is done on all namespaces.

    @return an object V1DaemonSetList containing a list of DaemonSets
    """
    # Enter a context with an instance of the API kubernetes.client
    with kubernetes.client.ApiClient(kube_client_config) as api_client:
        # Create an instance of the apps API
        api_instance_appsV1 = kubernetes.client.AppsV1Api(api_client)
        try:
            if namespace:
                daemon_set_list: V1DaemonSetList = api_instance_appsV1.list_namespaced_daemon_set(namespace=namespace)
            else:
                daemon_set_list: V1DaemonSetList = api_instance_appsV1.list_daemon_set_for_all_namespaces()
        except ApiException as error:
            logging.error("Exception when calling appsV1->list_daemon_set: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        return daemon_set_list


def check_installed_daemons(kube_client_config: kubernetes.client.Configuration) -> List[K8sDaemon]:
    """
    Check which daemons, among the known ones(see K8sDaemons enum), are present in the k8s cluster.

    @param kube_client_config the configuration of K8s on which the client is built.
    @return: The list of detected daemons
    """
    daemon_sets = get_daemon_sets(kube_client_config)
    to_return = []

    # For each daemon set, it looks if it there is some modules installed
    daemon: V1DaemonSet
    for daemon in daemon_sets.items:
        if 'app' in daemon.spec.selector.match_labels:
            if daemon.spec.selector.match_labels['app'] == K8sDaemon.FLANNEL.value:
                to_return.append(K8sDaemon.FLANNEL)
            if daemon.spec.selector.match_labels['app'] == K8sDaemon.METALLB.value:
                to_return.append(K8sDaemon.METALLB)
        if 'name' in daemon.spec.selector.match_labels:
            if daemon.spec.selector.match_labels['name'] == K8sDaemon.OPEN_EBS.value:
                to_return.append(K8sDaemon.OPEN_EBS)
    return to_return


def apply_def_to_cluster(kube_client_config: kubernetes.client.Configuration, dict_to_be_applied: dict = None,
                         yaml_file_to_be_applied: str = None):
    """
    This method can apply a definition to a k8s cluster. The data origin to apply can be a dictionary or a yaml file.

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
                result_yaml = kubernetes.utils.create_from_yaml(api_client, yaml_file_to_be_applied)
        except ApiException as error:
            logging.error("Exception when calling create_from_yaml: {}\n".format(error))
            raise error
        finally:
            api_client.close()
    return result_dict, result_yaml


def install_plugin_to_cluster(kube_client_config: kubernetes.client.Configuration, plugins_to_install: List[K8sDaemon]) -> dict:
    """
    Install a plugin list at the target k8s cluster.

    Args:
        kube_client_config: the configuration of K8s on which the client is built.
        plugins_to_install: List[K8sDaemon] the list of plugins to install on the cluster

    Returns:
        A dict[List[List[K8sTypes]: for each plugin a new key for the dictionary is created witch contains a list of resource types
        (V1Pod, V1DaemonSet, ...) and for each resource type there is a list of elements.

    Raises:
        ValueError if some plugins are already installed
    """
    version: K8sVersion = get_k8s_version(kube_client_config)
    installed_plugins = check_installed_daemons(kube_client_config)

    result : dict = {}

    # Checking if plugins to be installed have element in common with installed plugins
    common_elements = list(set(installed_plugins).intersection(plugins_to_install))
    if len(common_elements) > 0:
        raise ValueError("Plugins {} are already present in the cluster.".format(common_elements))

    for plugin in plugins_to_install:
        yaml_file_config = get_plugin_config_for_k8s_version(version, plugin)

        # Element in position one because apply_def_to_cluster is working on yaml file, please look at the source
        # code of apply_def_to_cluster
        result[plugin.value] = apply_def_to_cluster(kube_client_config, yaml_file_to_be_applied=yaml_file_config)[1]
    return result


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
            api_version: VersionInfo = version_api.get_code()
        except ApiException as error:
            logging.error("Exception when calling ApisApi->get_api_versions: {}\n".format(error))
            raise error
        finally:
            api_client.close()

        # Converting v.1.x.y -> v.1.x
        main_ver = api_version.git_version[:api_version.git_version.rfind('.')]
        if not K8sVersion.has_value(main_ver):
            raise ValueError("K8s version is not included among those provided")
        return K8sVersion(main_ver)


def parse_k8s_clusters_from_dict(k8s_list: dict) -> List[K8sModel]:
    """
    From a k8s cluster list in dictionary form returns a list of corresponding k8s models.

    @param k8s_list: dict to convert
    @return: a list of K8sModel objects
    """
    k8s_obj_list: List[K8sModel] = []
    for k8s in k8s_list:
        k8s_object = K8sModel.parse_obj(k8s)
        k8s_obj_list.append(k8s_object)
    return k8s_obj_list
