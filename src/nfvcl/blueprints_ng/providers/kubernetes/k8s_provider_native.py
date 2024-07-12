import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any

from pyhelm3 import Client

from nfvcl.blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderData
from nfvcl.blueprints_ng.providers.kubernetes.k8s_provider_interface import K8SProviderInterface, K8SProviderException
from nfvcl.blueprints_ng.resources import HelmChartResource
from nfvcl.models.k8s.topology_k8s_model import K8sModel
from nfvcl.rest_endpoints.k8s import get_k8s_cluster_by_area
from nfvcl.utils.k8s import get_k8s_config_from_file_content, get_services


class K8SProviderDataNative(BlueprintNGProviderData):
    pass


class K8SProviderNativeException(K8SProviderException):
    pass


helm_client_dict: Dict[int, Client] = {}


def get_helm_client_by_area(area: int):
    global helm_client_dict

    if area not in helm_client_dict:
        k8s_cluster: K8sModel = get_k8s_cluster_by_area(area)
        k8s_credential_file_path = Path(tempfile.gettempdir(), f"k8s_credential_{k8s_cluster.name}")
        with open(k8s_credential_file_path, mode="w") as k8s_credential_file:
            k8s_credential_file.write(k8s_cluster.credentials)

        helm_client_dict[area] = Client(kubeconfig=k8s_credential_file_path)

    return helm_client_dict[area]


class K8SProviderNative(K8SProviderInterface):
    def init(self):
        self.data: K8SProviderDataNative = K8SProviderDataNative()
        self.k8s_cluster: K8sModel = get_k8s_cluster_by_area(self.area)
        self.helm_client = get_helm_client_by_area(self.area)

    def install_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        self.logger.info(f"Installing Helm chart {helm_chart_resource.name}")

        chart = asyncio.run(self.helm_client.get_chart(
            helm_chart_resource.get_chart_converted(),
            repo=helm_chart_resource.repo,
            version=helm_chart_resource.version
        ))
        print(chart.metadata.name, chart.metadata.version)
        # print(asyncio.run(chart.readme()))

        # Install or upgrade a release
        revision = asyncio.run(self.helm_client.install_or_upgrade_release(
            helm_chart_resource.name.lower(),
            chart,
            values,
            namespace=helm_chart_resource.namespace.lower(),
            atomic=True,
            wait=True
        ))
        print(
            revision.release.name,
            revision.release.namespace,
            revision.revision,
            str(revision.status)
        )
        releases = asyncio.run(self.helm_client.list_releases(all=True, all_namespaces=True))
        for release in releases:
            revision = asyncio.run(release.current_revision())
            print(release.name, release.namespace, revision.revision, str(revision.status))

        self.save_to_db()

        k8s_config = get_k8s_config_from_file_content(self.k8s_cluster.credentials)
        services = get_services(kube_client_config=k8s_config, namespace=helm_chart_resource.namespace.lower())
        helm_chart_resource.set_services_from_k8s_api(services)

        self.logger.success(f"Installing Helm chart {helm_chart_resource.name} finished")
        self.save_to_db()

    def update_values_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        chart = asyncio.run(self.helm_client.get_chart(
            helm_chart_resource.get_chart_converted(),
            repo=helm_chart_resource.repo,
            version=helm_chart_resource.version
        ))
        print(chart.metadata.name, chart.metadata.version)
        # print(asyncio.run(chart.readme()))

        # Install or upgrade a release
        revision = asyncio.run(self.helm_client.install_or_upgrade_release(
            helm_chart_resource.name.lower(),
            chart,
            values,
            namespace=helm_chart_resource.namespace.lower(),
            atomic=True,
            wait=True
        ))
        print(
            revision.release.name,
            revision.release.namespace,
            revision.revision,
            str(revision.status)
        )
        self.save_to_db()

    def uninstall_helm_chart(self, helm_chart_resource: HelmChartResource):
        asyncio.run(self.helm_client.uninstall_release(
            helm_chart_resource.name.lower(),
            namespace=helm_chart_resource.namespace.lower(),
            wait=True
        ))
        self.save_to_db()

    def final_cleanup(self):
        pass
