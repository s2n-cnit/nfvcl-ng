import asyncio
import time
import traceback
from pathlib import Path
from typing import List

import yaml
from kubernetes.client import V1DaemonSet
from kubernetes.utils import FailToCreateError
from verboselogs import VerboseLogger

from nfvcl_core.utils.k8s.k8s_utils import get_k8s_config_from_file_content
from nfvcl_core.utils.log import create_logger
from nfvcl_core.utils.k8s.kube_api_utils import get_daemon_sets, apply_def_to_cluster, read_namespaced_storage_class, patch_namespaced_storage_class
from nfvcl_core.utils.file_utils import render_file_from_template_to_file, create_tmp_file
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_core_models.plugin_k8s_model import K8sPluginName, K8sPluginAdditionalData
from pyhelm3 import Client


def build_helm_client_from_credential_file_path(k8s_credential_file_path) -> Client:
    """
    Args:
        k8s_credential_file_path: Path to the Kubernetes credentials file to authenticate the Helm client.

    Returns:
        Client: An instance of the Helm client authenticated using the provided Kubernetes credentials file path.
    """
    return Client(kubeconfig=k8s_credential_file_path)


def build_helm_client_from_credential_file_content(k8s_credential_file_content, k8s_credential_file_path) -> Client:
    """
    Args:
        k8s_credential_file_content: The content of the Kubernetes credential file.
        k8s_credential_file_path: The file path where the Kubernetes credential file content will be written.

    Returns:
        Client: An instance of the Helm client authenticated using the provided Kubernetes credentials content.
    """
    with open(k8s_credential_file_path, mode="w") as k8s_credential_file:
        k8s_credential_file.write(k8s_credential_file_content)

    helm_client = Client(kubeconfig=k8s_credential_file_path)

    return helm_client


PLUGIN_PATH = Path("helm_charts/k8s_plugins/")
PLUGIN_VALUE_PATH = PLUGIN_PATH / 'values'


class HelmPluginManager:
    """
    Class for managing Helm plugins installation and operations within a Kubernetes environment.

    Attributes:
        k8s_credential_file (str): Path to the Kubernetes credential file.
        context_name (str, optional): Name of the context within the helm manager is working [default is ""].
    Methods:
        install_plugin(name, chart_name, version, namespace, values): Installs a Helm plugin with provided details.
        install_plugins(plugin_names, plugin_data): Installs multiple Helm plugins based on given names and additional data.
        _install_openebs(): Installs the OpenEBS plugin.
        _install_flannel(plugin_data): Installs the Flannel plugin with specific data.
        _install_metallb(plugin_data): Installs the MetalLB plugin with specific data.
        _install_calico(plugin_data): Installs the Calico plugin with specific data.
        get_installed_plugins(): Retrieves a list of currently installed Helm plugins.
        __apply_yaml_file_to_cluster(plugin_name, yaml_file_path): Applies a YAML file configuration to the Kubernetes cluster.
    """
    def __init__(self, k8s_credential_file, context_name: str = "") -> None:
        self.k8s_credential_file = k8s_credential_file
        self.k8s_config = get_k8s_config_from_file_content(k8s_credential_file)
        self.helm_client = build_helm_client_from_credential_file_content(k8s_credential_file, create_tmp_file("k8s", "k8s_helm_client_credentials", True))
        self.context_name = context_name
        self.logger: VerboseLogger = create_logger(self.__class__.__name__, blueprintid=context_name)

    def install_plugin(self, name: K8sPluginName, chart_name: str, version: str, namespace: str, values: dict):
        """
        Args:
            name: K8sPluginName, The name of the Kubernetes plugin to be installed.
            chart_name: str, The name of the Helm chart to be installed.
            version: str, The version of the Helm chart.
            namespace: str, The namespace in which the chart will be installed.
            values: dict, Additional values to be used during installation.
        """
        # HELM PLUGIN installation
        self.logger.debug(f"Loading chart {chart_name} from local charts")
        helm_chart_res: HelmChartResource = HelmChartResource(
            area=-100,  # NOT IMPORTANT in this util it is not used.
            name=name,
            chart=chart_name,
            chart_as_path=True,
            version=version,
            namespace=namespace
        )

        helm_client: Client = self.helm_client

        chart = asyncio.run(helm_client.get_chart(
            helm_chart_res.get_chart_converted(),
            repo=helm_chart_res.repo,
            version=helm_chart_res.version
        ))

        self.logger.info(f"Installing chart {chart} in {namespace}")
        asyncio.run(helm_client.install_or_upgrade_release(
            helm_chart_res.name.lower(),
            chart,
            values if values else {},
            namespace=helm_chart_res.namespace.lower(),
            atomic=True,
            wait=True
        ))

    def install_plugins(self, plugin_names: list[K8sPluginName], plugin_data: K8sPluginAdditionalData):
        """
        Args:
            plugin_names: list[K8sPluginName]: List of plugin names to be installed.
            plugin_data: K8sPluginAdditionalData: Additional data required for installing the plugins.
        """
        plugin_names_copy = plugin_names.copy()
        installed_plugins = self.get_installed_plugins()
        union = installed_plugins + plugin_names_copy
        if K8sPluginName.CALICO in union and K8sPluginName.FLANNEL in union:
            self.logger.error("CALICO and FLANNEL cannot be installed at the same time")
            raise Exception("CALICO and FLANNEL cannot be installed at the same time")
        # Check if there are already installed plugins
        for installed_plugin in installed_plugins:
            if installed_plugin in plugin_names_copy:
                self.logger.warning(f"Plugin {installed_plugin.name} is already installed, the installation will be skipped")
                plugin_names_copy.remove(installed_plugin)

        # Network plugins must be installed before the others
        if K8sPluginName.FLANNEL in plugin_names_copy:
            self._install_flannel(plugin_data)
            plugin_names_copy.remove(K8sPluginName.FLANNEL)
        if K8sPluginName.CALICO in plugin_names_copy:
            self._install_calico(plugin_data)
            plugin_names_copy.remove(K8sPluginName.CALICO)

        for plugin_name in plugin_names_copy:
            if plugin_name == K8sPluginName.OPEN_EBS:
                self._install_openebs()
            elif plugin_name == K8sPluginName.METALLB:
                self._install_metallb(plugin_data)

    def _install_openebs(self):
        """

        Installs OpenEBS plugin in Kubernetes cluster.

        Parameters:
        - self: The object instance.

        Returns:
        None

        """
        openebs_chart_path = PLUGIN_PATH / 'openebs-4.1.1.tgz'
        values_disable_replication = {"engines": {"replicated": {"mayastor": {"enabled": False}}}}
        self.install_plugin(
            name=K8sPluginName.OPEN_EBS,
            chart_name=str(openebs_chart_path),
            version="4.1.1",
            namespace="openebs",
            values=values_disable_replication
        )
        # Get the storage class to make it default
        storage_class = read_namespaced_storage_class(self.k8s_config, "openebs-hostpath")
        # Set it the default sc
        storage_class.metadata.annotations["storageclass.kubernetes.io/is-default-class"] = 'true'
        patch_namespaced_storage_class(self.k8s_config, storage_class)

    def _install_flannel(self, plugin_data: K8sPluginAdditionalData):
        """
        Args:
            plugin_data: K8sPluginAdditionalData object containing additional data needed to install the Flannel plugin
        """
        flannel_chart_path = PLUGIN_PATH / 'flannel-0.26.0.tgz'
        values = {"podCidr": plugin_data.pod_network_cidr if plugin_data.pod_network_cidr else "10.254.0.0/16"}
        self.install_plugin(
            name=K8sPluginName.FLANNEL,
            chart_name=str(flannel_chart_path),
            version="0.26.0",
            namespace="flannel",
            values=values
        )

    def _install_metallb(self, plugin_data: K8sPluginAdditionalData):
        """
        Args:
            plugin_data: K8sPluginAdditionalData used to fill values inside helm charts (i.e. the cidr of pods in flannel and calico)
        """
        metallb_chart_path = PLUGIN_PATH / 'metallb-0.14.8.tgz'
        self.install_plugin(
            name=K8sPluginName.METALLB,
            chart_name=str(metallb_chart_path),
            version="0.26.0",
            namespace="metallb",
            values={}
        )
        template_file_metallb = Path('src/nfvcl/config_templates/k8s/metallb/metallb-config.j2')
        rendered_file = render_file_from_template_to_file(template_file_metallb, plugin_data.model_dump(), self.context_name, ".yaml")
        self.__apply_yaml_file_to_cluster(K8sPluginName.METALLB, rendered_file)

    def _install_calico(self, plugin_data: K8sPluginAdditionalData):
        """
        Args:
            plugin_data: K8sPluginAdditionalData instance containing additional data relevant to the plugin installation process.
        """
        calico_chart_path = PLUGIN_PATH / 'tigera-operator-v3.29.0.tgz'
        calico_values = yaml.safe_load(PLUGIN_VALUE_PATH / 'calico.yaml')
        calico_values["installation"]["calicoNetwork"]["ipPools"][0]['cidr'] = plugin_data.pod_network_cidr if plugin_data.pod_network_cidr else "10.254.0.0/16"
        self.install_plugin(
            name=K8sPluginName.CALICO,
            chart_name=str(calico_chart_path),
            version="3.29.0",
            namespace="calico",
            values=calico_values
        )

    def get_installed_plugins(self) -> List[K8sPluginName]:
        """
        Method to retrieve the list of installed plugins within the Kubernetes cluster.

        Returns:
            List[K8sPluginName]: A list containing the names of the installed plugins.
        """
        daemon_sets = get_daemon_sets(self.k8s_config)
        # deployments = get_deployments(self.k8s_config)
        plugin_list = []

        daemon_set: V1DaemonSet
        for daemon_set in daemon_sets.items:
            if 'app' in daemon_set.metadata.labels:
                app = daemon_set.metadata.labels['app']
                match app:
                    case "flannel":
                        plugin_list.append(K8sPluginName.FLANNEL)
                    case "multus":
                        plugin_list.append(K8sPluginName.MULTUS)
                    case _:
                        pass
            if 'app.kubernetes.io/name' in daemon_set.metadata.labels:
                if daemon_set.metadata.labels['app.kubernetes.io/name'] == 'metallb':
                    plugin_list.append(K8sPluginName.METALLB)
            if 'openebs.io/component-name' in daemon_set.metadata.labels: # Value should be ndm
                if K8sPluginName.OPEN_EBS not in plugin_list:
                    plugin_list.append(K8sPluginName.OPEN_EBS)
            if 'k8s-app' in daemon_set.metadata.labels:  # Value should be calico-node
                if daemon_set.metadata.labels['k8s-app'] == 'calico-node':
                    plugin_list.append(K8sPluginName.CALICO)


        # for deployment in deployments.items:
        #     # If some plugin is detectable by the list of deployments
        #     pass

        return plugin_list

    def __apply_yaml_file_to_cluster(self, plugin_name: K8sPluginName, yaml_file_path: Path):
        """
        Apply the contents of a YAML file to a Kubernetes cluster.

        Args:
            plugin_name: The name of the Kubernetes plugin for which the YAML file is being applied.
            yaml_file_path: The path to the YAML file containing the Kubernetes definitions to be applied.
        """
        # Element in position 1 because apply_def_to_cluster is working on yaml file, please look at the source
        # code of apply_def_to_cluster
        try:
            apply_def_to_cluster(self.k8s_config, yaml_file_to_be_applied=yaml_file_path)[1]
        except FailToCreateError as fail:
            self.logger.warning(traceback.format_tb(fail.__traceback__))
            self.logger.warning("Definition <{}> for plugin <{}> has gone wrong. Retrying in 30 seconds...".format(str(yaml_file_path), plugin_name.name))
            time.sleep(30)
            apply_def_to_cluster(self.k8s_config, yaml_file_to_be_applied=yaml_file_path)[1]
