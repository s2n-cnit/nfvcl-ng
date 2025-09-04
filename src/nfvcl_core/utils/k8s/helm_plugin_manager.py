import asyncio
import time
import traceback
from pathlib import Path
from typing import List

import yaml
from kubernetes.client import V1DaemonSet
from kubernetes.utils import FailToCreateError
from pyhelm3 import Client
from verboselogs import VerboseLogger

from nfvcl_core.utils.file_utils import render_file_from_template_to_file, create_tmp_file
from nfvcl_core.utils.k8s.k8s_utils import get_k8s_config_from_file_content
from nfvcl_core.utils.k8s.kube_api_utils_class import KubeApiUtils
from nfvcl_core.utils.log import create_logger
from nfvcl_core_models.monitoring.k8s_monitoring import K8sMonitoring, DestinationType
from nfvcl_core_models.plugin_k8s_model import K8sPluginName, K8sPluginAdditionalData
from nfvcl_core_models.resources import HelmChartResource


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
        self.kube_utils = KubeApiUtils(self.k8s_config)
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

    def uninstall_plugin(self, namespace: str, wait=True):
        """
        Args:
            wait: True if uninstall should wait for completion.
            namespace: str, The namespace in which the chart will be installed.
        """

        helm_client: Client = self.helm_client
        releases = asyncio.run(helm_client.list_releases(namespace=namespace))
        self.logger.info(f"Uninstalling plugin in {namespace}")
        for release in releases:
            asyncio.run(helm_client.uninstall_release(release.name, namespace=namespace, wait=wait))

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
            elif plugin_name == K8sPluginName.MULTUS:
                self._install_multus(plugin_data)
            elif plugin_name == K8sPluginName.METALLB:
                self._install_metallb(plugin_data)
            elif plugin_name == K8sPluginName.CERT_MANAGER:
                self._install_cert_manager(plugin_data)
            elif plugin_name == K8sPluginName.NFVCL_WEBHOOK:
                self._install_nfvcl_webhook(plugin_data)

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
        storage_class = self.kube_utils.read_namespaced_storage_class("openebs-hostpath")
        # Set it the default sc
        storage_class.metadata.annotations["storageclass.kubernetes.io/is-default-class"] = 'true'
        self.kube_utils.patch_namespaced_storage_class(storage_class)

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

    def _install_multus(self, plugin_data: K8sPluginAdditionalData):
        multus_chart_path = PLUGIN_PATH / 'multus-cni-2.2.17.tgz'
        self.install_plugin(
            name=K8sPluginName.MULTUS,
            chart_name=str(multus_chart_path),
            version="2.2.17",
            namespace="multus",
            values={}
        )

    def install_k8s_monitoring(self, plugin_data: K8sPluginAdditionalData) -> K8sMonitoring:
        k8s_monitoring_chart_path = PLUGIN_PATH / 'k8s-monitoring-3.2.0.tgz'
        with open(PLUGIN_VALUE_PATH / 'k8s_monitoring.yaml', 'r') as k8s_monitoring_chart_path_values_file:
            k8s_monitoring_values = yaml.safe_load(k8s_monitoring_chart_path_values_file)
            k8s_monitoring_config = K8sMonitoring.model_validate(k8s_monitoring_values)
            k8s_monitoring_config.cluster.name = plugin_data.k8smonitoring_cluster_id
            k8s_monitoring_config.cluster.namespace = f"alloy-metrics"

            if plugin_data.loki:
                k8s_monitoring_config.add_destination(
                    name=f"loki-{plugin_data.loki.id}",
                    _type=DestinationType.LOKI,
                    url=f"http://{plugin_data.loki.ip}:{plugin_data.loki.port}/loki/api/v1/push",
                    username=plugin_data.loki.user,
                    password=plugin_data.loki.password
                )

            if plugin_data.prometheus:
                k8s_monitoring_config.add_destination(
                    name=f"prometheus-{plugin_data.prometheus.id}",
                    _type=DestinationType.PROMETHEUS,
                    url=f"http://{plugin_data.prometheus.ip}:{plugin_data.prometheus.port}/api/v1/write",
                    username=plugin_data.prometheus.user,
                    password=plugin_data.prometheus.password
                )
            if plugin_data.k8smonitoring_node_exporter_enabled:
                k8s_monitoring_config.enable_node_exporter(plugin_data.k8smonitoring_node_exporter_label)

        self.install_plugin(
            name=K8sPluginName.K8S_MONITORING,
            chart_name=str(k8s_monitoring_chart_path),
            version="3.2.0",
            namespace=k8s_monitoring_config.cluster.namespace,
            values=k8s_monitoring_config.model_dump(exclude_none=True, by_alias=True)
        )
        return k8s_monitoring_config

    def add_metrics_destination(self, plugin_data: K8sPluginAdditionalData):
        k8s_monitoring_chart_path = PLUGIN_PATH / 'k8s-monitoring-3.2.0.tgz'
        tmp = plugin_data.k8smonitoring_config.__deepcopy__()
        if plugin_data.loki:
            plugin_data.k8smonitoring_config.add_destination(
                name=f"loki-{plugin_data.loki.id}",
                _type=DestinationType.LOKI,
                url=f"http://{plugin_data.loki.ip}:{plugin_data.loki.port}/loki/api/v1/push",
                username=plugin_data.loki.user,
                password=plugin_data.loki.password
            )

        if plugin_data.prometheus:
            plugin_data.k8smonitoring_config.add_destination(
                name=f"prometheus-{plugin_data.prometheus.id}",
                _type=DestinationType.PROMETHEUS,
                url=f"http://{plugin_data.prometheus.ip}:{plugin_data.prometheus.port}/api/v1/write",
                username=plugin_data.prometheus.user,
                password=plugin_data.prometheus.password
            )

        if tmp != plugin_data.k8smonitoring_config:
            self.install_plugin(
                name=K8sPluginName.K8S_MONITORING,
                chart_name=str(k8s_monitoring_chart_path),
                version="3.2.0",
                namespace=plugin_data.k8smonitoring_config.cluster.namespace,
                values=plugin_data.k8smonitoring_config.model_dump(exclude_none=True, by_alias=True)
            )
            return plugin_data.k8smonitoring_config
        return tmp

    def del_metrics_destination(self, plugin_data: K8sPluginAdditionalData):
        k8s_monitoring_chart_path = PLUGIN_PATH / 'k8s-monitoring-3.2.0.tgz'
        tmp = plugin_data.k8smonitoring_config.__deepcopy__()
        if plugin_data.loki:
            plugin_data.k8smonitoring_config.del_destination(name=f"loki-{plugin_data.loki.id}")

        if plugin_data.prometheus:
            plugin_data.k8smonitoring_config.del_destination(name=f"prometheus-{plugin_data.prometheus.id}")

        if tmp != plugin_data.k8smonitoring_config:
            self.install_plugin(
                name=K8sPluginName.K8S_MONITORING,
                chart_name=str(k8s_monitoring_chart_path),
                version="3.2.0",
                namespace=plugin_data.k8smonitoring_config.cluster.namespace,
                values=plugin_data.k8smonitoring_config.model_dump(exclude_none=True, by_alias=True)
            )
            return plugin_data.k8smonitoring_config
        return tmp

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

    def _install_cert_manager(self, plugin_data: K8sPluginAdditionalData):
        """
        Args:
            plugin_data: K8sPluginAdditionalData used to fill values inside helm charts (i.e. the cidr of pods in flannel and calico)
        """
        cert_manager_chart_path = PLUGIN_PATH / 'cert-manager-v1.18.0.tgz'
        self.install_plugin(
            name=K8sPluginName.CERT_MANAGER,
            chart_name=str(cert_manager_chart_path),
            version="v1.18.0",
            namespace="cert-manager",
            values={"crds": {"enabled": True}}
        )

    def _install_nfvcl_webhook(self, plugin_data: K8sPluginAdditionalData):
        base_path = Path("src/nfvcl/config_templates/k8s/nfvcl_webhook")

        template_file_certificates = Path(base_path, "certificate.yaml")
        template_file_deployment = Path(base_path, "deployment.yaml")
        template_file_webhook = Path(base_path, "mutatingwebhookconfiguration.yaml.j2")

        rendered_file_certificates = render_file_from_template_to_file(template_file_certificates, plugin_data.model_dump(), self.context_name, ".yaml")
        rendered_file_deployment = render_file_from_template_to_file(template_file_deployment, plugin_data.model_dump(), self.context_name, ".yaml")
        self.__apply_yaml_file_to_cluster(K8sPluginName.NFVCL_WEBHOOK, rendered_file_certificates)
        self.__apply_yaml_file_to_cluster(K8sPluginName.NFVCL_WEBHOOK, rendered_file_deployment)

        # Poll until the secret is available
        max_retries = 30
        retry_interval = 1  # seconds
        ca_b64 = None
        for attempt in range(max_retries):
            try:
                secret = self.kube_utils.get_secrets("nfvcl-webhook", "webhook-tls")
                if secret and secret.items and len(secret.items) > 0 and "ca.crt" in secret.items[0].data:
                    ca_b64 = secret.items[0].data["ca.crt"]
                    break
                self.logger.debug(f"Secret not ready yet, waiting (attempt {attempt + 1}/{max_retries})...")
            except Exception as e:
                self.logger.debug(f"Error retrieving secret: {e}")

            time.sleep(retry_interval)
        else:
            self.logger.error("Timed out waiting for webhook-tls secret")
            raise TimeoutError("Timed out waiting for webhook-tls secret to become available")

        if ca_b64:
            rendered_file_webhook = render_file_from_template_to_file(template_file_webhook, {"cabundle": ca_b64}, self.context_name, ".yaml")
            self.__apply_yaml_file_to_cluster(K8sPluginName.NFVCL_WEBHOOK, rendered_file_webhook)

    def _install_calico(self, plugin_data: K8sPluginAdditionalData):
        """
        Args:
            plugin_data: K8sPluginAdditionalData instance containing additional data relevant to the plugin installation process.
        """
        calico_chart_path = PLUGIN_PATH / 'tigera-operator-v3.30.1.tgz'
        with open(PLUGIN_VALUE_PATH / 'calico.yaml', 'r') as calico_values_file:
            calico_values = yaml.safe_load(calico_values_file)
        calico_values["installation"]["calicoNetwork"]["ipPools"][0]['cidr'] = plugin_data.pod_network_cidr if plugin_data.pod_network_cidr else "10.254.0.0/16"
        self.install_plugin(
            name=K8sPluginName.CALICO,
            chart_name=str(calico_chart_path),
            version="3.30.1",
            namespace="tigera-operator",
            values=calico_values
        )

    def get_installed_plugins(self) -> List[K8sPluginName]:
        """
        Method to retrieve the list of installed plugins within the Kubernetes cluster.

        Returns:
            List[K8sPluginName]: A list containing the names of the installed plugins.
        """
        daemon_sets = self.kube_utils.get_daemon_sets()
        # deployments = get_deployments(self.k8s_config)
        plugin_list = []

        daemon_set: V1DaemonSet
        for daemon_set in daemon_sets.items:
            if daemon_set.metadata.labels is None:
                continue
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
            if 'openebs.io/component-name' in daemon_set.metadata.labels:  # Value should be ndm
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
            self.kube_utils.apply_def_to_cluster(yaml_file_to_be_applied=yaml_file_path)[1]
        except FailToCreateError as fail:
            self.logger.warning(traceback.format_tb(fail.__traceback__))
            self.logger.warning("Definition <{}> for plugin <{}> has gone wrong. Retrying in 30 seconds...".format(str(yaml_file_path), plugin_name.name))
            time.sleep(30)
            self.kube_utils.apply_def_to_cluster(yaml_file_to_be_applied=yaml_file_path)[1]
