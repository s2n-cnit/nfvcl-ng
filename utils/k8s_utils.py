from models.k8s import K8sModel, K8sDaemons
from typing import List
import kubernetes.client
from kubernetes.client import Configuration, V1PodList, V1DaemonSetList, V1DaemonSet
from kubernetes import config
from kubernetes.client.rest import ApiException
import tempfile


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
            raise error
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
            raise error
        return daemon_set_list


def check_installed_daemons(kube_client_config: kubernetes.client.Configuration) -> List[K8sDaemons]:
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
            if daemon.spec.selector.match_labels['app'] == K8sDaemons.FLANNEL.value:
                to_return.append(K8sDaemons.FLANNEL)
            if daemon.spec.selector.match_labels['app'] == K8sDaemons.METALLB.value:
                to_return.append(K8sDaemons.METALLB)
        if 'name' in daemon.spec.selector.match_labels:
            if daemon.spec.selector.match_labels['name'] == K8sDaemons.OPEN_EBS.value:
                to_return.append(K8sDaemons.OPEN_EBS)
    return to_return


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
