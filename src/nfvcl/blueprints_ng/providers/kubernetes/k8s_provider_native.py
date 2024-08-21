import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

import pyhelm3.errors
import yaml
from kubernetes.client import V1PodList
from pydantic import Field
from pyhelm3 import Client, ReleaseRevisionStatus

from nfvcl.blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderData
from nfvcl.blueprints_ng.providers.kubernetes.k8s_provider_interface import K8SProviderInterface, K8SProviderException
from nfvcl.blueprints_ng.resources import HelmChartResource
from nfvcl.models.k8s.topology_k8s_model import TopologyK8sModel
from nfvcl.rest_endpoints.k8s import get_k8s_cluster_by_area
from nfvcl.topology.topology import build_topology
from nfvcl.utils.k8s import get_k8s_config_from_file_content, get_services, get_deployments, k8s_delete_namespace, \
    get_pods_for_k8s_namespace

HELM_TMP_FOLDER_PATH = Path(tempfile.gettempdir()) / 'nfvcl/helm'
HELM_TMP_FOLDER_PATH.mkdir(parents=True, exist_ok=True)


class K8SProviderDataNative(BlueprintNGProviderData):
    namespaces: Optional[List[str]] = Field(default_factory=list)


class K8SProviderNativeException(K8SProviderException):
    pass


helm_client_dict: Dict[int, Client] = {}


def get_helm_client_by_area(area: int) -> Client:
    """
    Returns the helm client for the K8S cluster in the given area
    Args:
        area: The area in which the client is built

    Returns:
        The client for the K8S cluster in the given area
    """
    global helm_client_dict

    k8s_cluster: TopologyK8sModel = get_k8s_cluster_by_area(area)
    k8s_credential_file_path = HELM_TMP_FOLDER_PATH / f"k8s_credential_{k8s_cluster.name}"
    # If helm client does not exist for an area or the cluster for the area have changed without restart of NFVCL
    if area not in helm_client_dict or not (helm_client_dict[area]._command._kubeconfig == k8s_credential_file_path):
        k8s_cluster: TopologyK8sModel = get_k8s_cluster_by_area(area)
        k8s_credential_file_path = HELM_TMP_FOLDER_PATH / f"k8s_credential_{k8s_cluster.name}"
        with open(k8s_credential_file_path, mode="w") as k8s_credential_file:
            k8s_credential_file.write(k8s_cluster.credentials)

        helm_client_dict[area] = Client(kubeconfig=k8s_credential_file_path)

    return helm_client_dict[area]


class K8SProviderNative(K8SProviderInterface):
    def init(self):
        self.data: K8SProviderDataNative = K8SProviderDataNative()
        self.k8s_cluster: TopologyK8sModel = get_k8s_cluster_by_area(self.area)
        self.helm_client = get_helm_client_by_area(self.area)

    def install_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        self.logger.info(f"Installing Helm chart {helm_chart_resource.name}")

        chart = asyncio.run(self.helm_client.get_chart(
            helm_chart_resource.get_chart_converted(),
            repo=helm_chart_resource.repo,
            version=helm_chart_resource.version
        ))

        self.logger.debug(f"Helm chart internal name: {chart.metadata.name}, version: {chart.metadata.version}")

        # Install or upgrade a release, if fails print debug cmd to reproduce locally the error with debug option. Pyhelm3 does not support debug option.
        try:
            revision = asyncio.run(self.helm_client.install_or_upgrade_release(
                helm_chart_resource.name.lower(),
                chart,
                values,
                namespace=helm_chart_resource.namespace.lower(),
                atomic=True,
                wait=True
            ))
        except pyhelm3.errors.Error as helmError:
            self.logger.error(f"Helm chart deployment failed. You can debug installation in this way from nfvcl folder:\n{self._generate_debug_cmd_cli(helm_chart_resource, values, chart.metadata.version)}")
            raise helmError

        if helm_chart_resource.namespace.lower() not in self.data.namespaces:
            self.data.namespaces.append(helm_chart_resource.namespace.lower())

        self.logger.debug(f"Helm chart installed name: {revision.release.name}, namespace: {revision.release.namespace}, revision: {revision.revision}, status: {str(revision.status)}")

        self.save_to_db()

        if not self._check_helm_chart_status(revision.release.name, revision.release.namespace, ReleaseRevisionStatus.DEPLOYED):
            self.logger.error(f"The helm chart '{helm_chart_resource.name}' is not in the DEPLOYED state")
            raise K8SProviderNativeException(f"The helm chart '{helm_chart_resource.name}' is not in the DEPLOYED state")

        # Adding this blueprint to the deployed list on the cluster
        topo = build_topology()
        cluster = topo.get_k8s_cluster_by_area(self.area)
        cluster.deployed_blueprints.append(self.blueprint_id)
        topo.update_k8scluster(cluster)

        k8s_config = get_k8s_config_from_file_content(self.k8s_cluster.credentials)
        services = get_services(kube_client_config=k8s_config, namespace=helm_chart_resource.namespace.lower())
        deployments = get_deployments(kube_client_config=k8s_config, namespace=helm_chart_resource.namespace.lower())

        deployments_pods: Dict[str, V1PodList] = {}

        for deployment in deployments.items:
            deployment_pods = get_pods_for_k8s_namespace(k8s_config, namespace=helm_chart_resource.namespace.lower(), label_selector=','.join([f'{k}={v}' for k, v in deployment.spec.selector.match_labels.items()]))
            deployments_pods[deployment.metadata.name] = deployment_pods

        helm_chart_resource.set_services_from_k8s_api(services)
        helm_chart_resource.set_deployments_from_k8s_api(deployments, deployments_pods)

        self.logger.success(f"Installing Helm chart {helm_chart_resource.name} finished")
        self.save_to_db()

    def _generate_debug_cmd_cli(self, helm_chart_resource, values, version):
        """
        Generates a shell cmd to reproduce and debug the helm chart installation on NFVCL machine
        Args:
            helm_chart_resource: the chart
            values: helm chart values
            version: The version of the chart

        Returns:
            The command to be executed in the NFVCL folder
        """
        values_path = HELM_TMP_FOLDER_PATH / f"{helm_chart_resource.namespace.lower()}_{helm_chart_resource.name}.yaml"
        yaml_content = yaml.dump(values)
        values_path.write_text(yaml_content)
        k8s_credential_path = HELM_TMP_FOLDER_PATH / f"k8s_credential_{self.k8s_cluster.name}"
        return f"helm upgrade {helm_chart_resource.name} {helm_chart_resource.get_chart_converted()} --history-max 10 --install --output json --timeout 5m --values '{values_path.absolute()}' --debug --atomic --create-namespace --namespace {helm_chart_resource.namespace.lower()} --version {version} --wait --wait-for-jobs --kubeconfig {k8s_credential_path.absolute()}"

    def _check_if_helm_chart_installed(self, release_name: str, release_namespace: str):
        releases = asyncio.run(self.helm_client.list_releases(all=True, all_namespaces=True))
        for release in releases:
            if release.name == release_name and release.namespace == release_namespace:
                return True
        return False

    def _check_helm_chart_status(self, release_name: str, release_namespace: str, desired_status: ReleaseRevisionStatus):
        releases = asyncio.run(self.helm_client.list_releases(all=True, all_namespaces=True))
        for release in releases:
            revision = asyncio.run(release.current_revision())
            if release.name == release_name and release.namespace == release_namespace:
                return revision.status == desired_status
        raise K8SProviderNativeException(f"Unable to check Helm chart status for '{release_name}', namespace '{release_namespace}', not found")

    def update_values_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        self.logger.info(f"Updating Helm chart {helm_chart_resource.name}")

        chart = asyncio.run(self.helm_client.get_chart(
            helm_chart_resource.get_chart_converted(),
            repo=helm_chart_resource.repo,
            version=helm_chart_resource.version
        ))
        self.logger.debug(f"Helm chart {helm_chart_resource.name} metadata version: {chart.metadata.version}")

        # Install or upgrade a release
        revision = asyncio.run(self.helm_client.install_or_upgrade_release(
            helm_chart_resource.name.lower(),
            chart,
            values,
            namespace=helm_chart_resource.namespace.lower(),
            atomic=True,
            wait=True
        ))

        if not self._check_helm_chart_status(revision.release.name, revision.release.namespace, ReleaseRevisionStatus.DEPLOYED):
            self.logger.error(f"The helm chart '{helm_chart_resource.name}' is not in the DEPLOYED state")
            raise K8SProviderNativeException(f"The helm chart '{helm_chart_resource.name}' is not in the DEPLOYED state")

        self.save_to_db()

        self.logger.success(f"Updated Helm chart {helm_chart_resource.name}")

    def uninstall_helm_chart(self, helm_chart_resource: HelmChartResource):
        self.logger.info(f"Uninstalling Helm chart {helm_chart_resource.name}")

        asyncio.run(self.helm_client.uninstall_release(
            helm_chart_resource.name.lower(),
            namespace=helm_chart_resource.namespace.lower(),
            wait=True
        ))
        self.save_to_db()

        if self._check_if_helm_chart_installed(helm_chart_resource.name.lower(), helm_chart_resource.namespace.lower()):
            self.logger.error(f"The helm chart '{helm_chart_resource.name}' was not uninstalled successfully")
            raise K8SProviderNativeException(f"The helm chart '{helm_chart_resource.name}' was not uninstalled successfully")

        # Removing this blueprint to the deployed list on the cluster
        try:
            topo = build_topology()
            cluster = topo.get_k8s_cluster_by_area(self.area)
            cluster.deployed_blueprints.remove(self.blueprint_id)
            topo.update_k8scluster(cluster)
        except ValueError as e:
            self.logger.warning("Blueprint has not been found in the cluster deployed blueprints")

        self.logger.success(f"Uninstalled Helm chart {helm_chart_resource.name}")

    def final_cleanup(self):
        self.logger.info(f"Performing k8s final cleanup")
        k8s_config = get_k8s_config_from_file_content(self.k8s_cluster.credentials)
        for ns in self.data.namespaces:
            self.logger.debug(f"Deleting k8s namespace '{ns}'")
            k8s_delete_namespace(k8s_config, ns)
