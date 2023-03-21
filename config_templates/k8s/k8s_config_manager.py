from models.k8s import K8sVersion, K8sDaemon
import os


def get_plugin_config_for_k8s_version(k8s_version: K8sVersion, plugin: K8sDaemon):
    base_path = './config_templates/k8s/'
    dir_path = base_path + plugin.value

    target_file = None

    for path in os.listdir(dir_path):
        # File name is something like v1.17-v1.27_flannel.yml
        # Remove the second part, the plugin name
        version_part = path.split('_')[0]
        # Splitting upper and lowe version
        versions = version_part.split('-')

        # Removing the v
        for i in range(0, len(versions)):
            versions[i] = versions[i][1:]

        desired_version = k8s_version.value[1:]

        if float(versions[0]) <= float(desired_version) <= float(versions[1]):
            target_file = path
            break

    if target_file:
        return dir_path + '/' + target_file
    else:
        raise ValueError("There is no {} config file for kubernetes {}.".format(plugin.value, k8s_version.value))
