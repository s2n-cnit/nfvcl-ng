from models.k8s import K8sVersion, K8sDaemon
import os


def get_plugin_config_for_k8s_version(k8s_version: K8sVersion, plugin: K8sDaemon) -> str:
    """
    Look for plugins yaml to be applied to a k8s cluster. Files are searched in folders that have the same of the plugin.
    For each plugin we can have different files for each k8s cluster version.
    This method looks if the k8s cluster is compatible with any of the files for a plugin.
    The format of the files is 'v1.17-v1.27_flannel.yml' to have an upper and lower bound and 'v1.17+' to give only a
    lower bound.

    Args:
        k8s_version: [K8sVersion] the version of the k8s cluster

        plugin: [K8sDaemon] the plugin to be installed.

    Returns:
        str: a string that represent the path to the correct file to be applied at the cluster.

    Raises:
        ValueError: on missing config file for a plugin, on malformed file name.
    """
    base_path = './config_templates/k8s/'
    dir_path = base_path + plugin.value

    target_file = None

    for path in os.listdir(dir_path):
        # File name is something like 'v1.17-v1.27_flannel.yml' or v1.17-v1.17_flannel.yml or v1.17+_flannel.yml
        # Remove the second part, the plugin name so that we obtain 'v1.17-v1.27' or v1.17+
        version_part = path.split('_')[0]
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
                raise ValueError("Filename {} is malformed.".format(path))
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
                target_file = path
                break

    if target_file:
        return dir_path + '/' + target_file
    else:
        raise ValueError("There is not available {} plugin version compatible with k8s cluster version {}"
                         .format(plugin.value, k8s_version.value))
