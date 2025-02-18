import tempfile
from logging import Logger
from typing import List

import kubernetes.client
import kubernetes.utils
from kubernetes import config
from kubernetes.client import Configuration
from nfvcl_core_models.plugin_k8s_model import K8sPluginName
from nfvcl_core_models.topology_k8s_model import K8sVersion
from nfvcl_core.utils.k8s.kube_api_utils import get_k8s_version
from nfvcl_core.utils.log import create_logger

logger: Logger = create_logger("K8S UTILS")


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
                        msg_err = "The version of k8s cluster is too low. Requested APIs for this method are not implemented."
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
    kube_client_config = type.__call__(Configuration)

    try:
        with open(tmp.name, 'w') as f:
            f.write(kube_client_config_file_content)
        tmp.flush()

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
    config.load_kube_config_from_dict(config_file=kube_client_config_dict, context=None, client_configuration=kube_client_config, persist_config=False)
    kube_client_config.verify_ssl = False

    return kube_client_config


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
