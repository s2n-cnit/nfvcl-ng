from logging import Logger
from typing import List

import os
import json
from models.k8s.topology_k8s_model import K8sVersion, K8sPluginName, K8sPlugin
from utils.log import create_logger

PLUGIN_BASE_PATH = './config_templates/k8s/'

logger: Logger = create_logger("K8S PLUGIN MANAGER")


def get_enabled_plugins(plugin_names_filter: List[K8sPluginName] = None) -> List[K8sPlugin]:
    """
    Return a filtered list of enabled plugins from the plugin whose conf files we want from enabled-plugins.json

    Args:
        plugin_names_filter: the filter, on plugin name, to be applied before returning the list. Set to None means
        there will be no filter

    Returns:
        A filtered List[K8sPlugin] of enabled plugins
    """
    enabled_plugins: List[K8sPlugin] = []

    # Reading the file of enabled plugins
    plug_file = open(PLUGIN_BASE_PATH+"/enabled-plugins.json", 'r')
    data = plug_file.read()
    json_data: List[dict] = json.loads(data)

    for dict_plugin in json_data:
        plugin: K8sPlugin = K8sPlugin.parse_obj(dict_plugin)
        # If no filter
        if plugin_names_filter is None:
            enabled_plugins.append(plugin)
        # If filter
        elif plugin.name in plugin_names_filter:
            enabled_plugins.append(plugin)
    # Closing file
    plug_file.close()

    return enabled_plugins


def get_plugin_config_files(k8s_version: K8sVersion, plugin_folder_path: str) -> List:
    """
    Look for plugins yaml to be applied to a k8s cluster.
    For each plugin we can have different files depending on k8s cluster version.
    For each plugin we can have different modules to be applied, for a certain version of k8s.
    This method looks if the k8s cluster is compatible with any of the files for a plugin folder.
    The format of the files is 'v1.17-v1.27_flannel.yml' to have an upper and lower bound and 'v1.17+' to give only a
    lower bound.

    Args:
        k8s_version: [K8sVersion] the version of the k8s cluster

        plugin_folder_path: [K8sDaemon] the folder of plugin to be installed.

    Returns:
        List[tuple[str,str]]: a list of tuple (module_path, module_name) that represent compatible modules that can be applied
        at the cluster. module_path is the path to the file. The module_name is the name of the module and should be
        coherent with values in enabled-plugins.json file.

    Raises:
        ValueError: on missing config file for a plugin, on malformed file name.
    """

    target_modules = []

    for path in os.listdir(plugin_folder_path):
        # File name is something like 'v1.17-v1.27_plugin_module.yml' or v1.17-v1.17_plugin.yml or v1.17+_plugin_module.yml
        split = path.split('_')

        if len(split) <= 1:
            raise ValueError("Filename ->{}<- is malformed. E.g. v1.18+_module-name.yaml or v1.17-v1.17_plugin-name.yml".format(path))

        # ------ Working on the module name
        # The part where there is the module name
        module_name_part = split[1]
        module_name = module_name_part.split('.')[0]

        # ------ Working on the version
        # Remove the second part, the plugin name so that we obtain 'v1.17-v1.27' or v1.17+
        version_part = split[0]
        # Splitting upper and lowe version
        versions = version_part.split('-')

        lower_version: float = 0.0
        upper_version: float = 0.0
        no_upper_limit: bool = False

        # First case 'v1.17+'
        if len(versions) == 1:
            if versions[0][-1] == '+':
                no_upper_limit = True
                # Removing the last char (+) and the first one (v) with [1:-1] and then converting to float
                lower_version = float(versions[0][1:-1])
            else:
                raise ValueError("Filename ->{}<- is malformed. E.g. v1.18+_module-name.yaml or v1.17-v1.17_plugin-name.yml".format(path))
        # Second case 'v1.17-v1.27'
        elif len(versions) == 2:
            # Removing the v from v1.x and v 1.y
            for i in range(0, len(versions)):
                versions[i] = versions[i][1:]
            lower_version = float(versions[0])
            upper_version = float(versions[1])
        else:
            raise ValueError("Filename {} is malformed.".format(path))

        # Removing the v from desired version value and converting to float
        cluster_version = float(k8s_version.value[1:])

        # Check if k8s version is not too low
        if lower_version < cluster_version:
            # Check if k8s version is not too high
            if cluster_version < upper_version or no_upper_limit:
                target_modules.append((plugin_folder_path + '/' + path, module_name))

    if len(target_modules) > 0:
        return target_modules
    else:
        raise ValueError("There is not available plugin version in {} compatible with k8s cluster version {}"
                         .format(plugin_folder_path, k8s_version.value))


def check_order_files_for_plugin(required_module_order: List[str], found_module_order: List[str],
                                 module_file_list: List[str]) -> List[str]:
    """
    Reorder the files in the file list consistently with the required order.

    Args:
        required_module_order: the list of modules in the desired order. It should be retrieved from
        enabled-plugins.json, after file has been parsed.

        found_module_order: the list of modules in the current order. The order of this list is closely linked to the
        next argument (module_file_list)

        module_file_list: the list to be ordered. It contains the path of file corresponding to modules in
        (found_module_order).

    Returns:
        the ordered list
    """
    # Checking that have the same lenght. They containe the same elements, only the order can change.
    assert len(required_module_order) == len(found_module_order)
    # If one element -> already ordered
    if len(required_module_order) <= 1:
        return module_file_list
    else:
        ordered_list: List[str] = []

        # Creating new order
        for i in range(0, len(required_module_order)):
            index_of = found_module_order.index(required_module_order[i])
            ordered_list.append(module_file_list[index_of])
        return ordered_list


def get_yaml_files_for_plugin(k8s_version: K8sVersion, plugin: K8sPluginName) -> List[str]:
    """
    Get yaml file paths to be applied for installing a plugin on a cluster.
    Checks if the plugin is enabled.
    Retrieve the modules files for the specific k8s version.
    Checks that we have found all modules for the plugin from enabled-plugins.json
    Check the order of yaml to be applied for the plugin.

    Args:
        k8s_version: The version of the k8s cluster.

        plugin: the plugin whose configuration files we want to retrieve

    Returns:
        A ordered List[str] representing path of files to be applied at a k8s cluster, in the correct order, to install
        the desired plugin.
    """
    # Checking between enabled plugins if there is the desired one
    enable_plugins = get_enabled_plugins()
    enable_compatible_plugins = [enabled_plug for enabled_plug in enable_plugins if enabled_plug.name == plugin.value]
    if len(enable_compatible_plugins) <= 0:
        err_msg = "Plugin [{}] not found in enabled plugins.".format(plugin)
        logger.error(err_msg)
        raise ValueError(err_msg)

    # Getting the first match (there should be only one)
    target_plugin = enable_compatible_plugins[0]
    # Getting the files for a plugin compatible with current k8s version
    dir_path = PLUGIN_BASE_PATH + target_plugin.name
    found_plugins: List = get_plugin_config_files(k8s_version=k8s_version, plugin_folder_path=dir_path)
    # Position 1 in the tuple contains the modules name
    found_modules = [plugin[1] for plugin in found_plugins]
    # Position 1 in the tuple contains the path of files (for each module)
    found_modules_paths = [plugin[0] for plugin in found_plugins]

    # Checking that the retrieved modules for the plugin correspond with the expected number (from enabled-plugins.json)
    if len(found_modules) == len(target_plugin.installation_modules):
        differing_elements = list(set(found_modules).difference(target_plugin.installation_modules))
        if len(differing_elements) > 0:
            raise ValueError("Missing module files {} for plugin {}.".format(differing_elements, plugin))
        else:
            # Checking that the order is the same of enabled-plugins.json
            found_modules_paths = check_order_files_for_plugin(required_module_order=target_plugin.installation_modules,
                                                               found_module_order=found_modules,
                                                               module_file_list=found_modules_paths)
            return found_modules_paths
    else:
        raise ValueError("Compatible found modules number for {} plugin and k8s version {} does not match required"
                         " number of modules.".format(plugin, k8s_version))