import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any

from blueprints_ng.resources import HelmChartResource
from pyhelm3 import Client

from blueprints_ng.providers.blueprint_ng_provider_interface import *
from blueprints_ng.providers.kubernetes.k8s_provider_interface import K8SProviderInterface, K8SProviderException
from models.k8s.topology_k8s_model import K8sModel
from rest_endpoints.k8s import get_k8s_cluster_by_area
from topology.topology import build_topology


class K8SProviderDataNative(BlueprintNGProviderData):
    pass


class K8SProviderNativeException(K8SProviderException):
    pass


helm_client_dict: Dict[int, Client] = {}
# # TODO find a better way
global_topology = build_topology()


class K8SProviderNative(K8SProviderInterface):
    def init(self):
        self.data: K8SProviderDataNative = K8SProviderDataNative()

    def __get_helm_client_by_area(self, area: int):
        global helm_client_dict

        if area in helm_client_dict:
            return helm_client_dict[area]

        k8s_cluster: K8sModel = get_k8s_cluster_by_area(area)
        k8s_credential_file_path = Path(tempfile.gettempdir(), f"k8s_credential_{k8s_cluster.name}")
        with open(k8s_credential_file_path, mode="w") as k8s_credential_file:
            k8s_credential_file.write(k8s_cluster.credentials)

        helm_client = Client(kubeconfig=k8s_credential_file_path)
        helm_client_dict[area] = helm_client
        return helm_client

    def install_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        helm_client = self.__get_helm_client_by_area(helm_chart_resource.area)

        self.logger.info(f"Installing Helm chart {helm_chart_resource.name}")

        chart = asyncio.run(helm_client.get_chart(
            helm_chart_resource.get_chart_converted(),
            repo=helm_chart_resource.repo,
            version=helm_chart_resource.version
        ))
        print(chart.metadata.name, chart.metadata.version)
        # print(asyncio.run(chart.readme()))

        # Install or upgrade a release
        revision = asyncio.run(helm_client.install_or_upgrade_release(
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
        releases = asyncio.run(helm_client.list_releases(all=True, all_namespaces=True))
        for release in releases:
            revision = asyncio.run(release.current_revision())
            print(release.name, release.namespace, revision.revision, str(revision.status))

        self.logger.success(f"Installing Helm chart {helm_chart_resource.name} finished")
        self.blueprint.to_db()

    def update_values_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        helm_client = self.__get_helm_client_by_area(helm_chart_resource.area)

        chart = asyncio.run(helm_client.get_chart(
            helm_chart_resource.get_chart_converted(),
            repo=helm_chart_resource.repo,
            version=helm_chart_resource.version
        ))
        print(chart.metadata.name, chart.metadata.version)
        # print(asyncio.run(chart.readme()))

        # Install or upgrade a release
        revision = asyncio.run(helm_client.install_or_upgrade_release(
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
        self.blueprint.to_db()

    def uninstall_helm_chart(self, helm_chart_resource: HelmChartResource):
        helm_client = self.__get_helm_client_by_area(helm_chart_resource.area)

        asyncio.run(helm_client.uninstall_release(
            helm_chart_resource.name.lower(),
            namespace=helm_chart_resource.namespace.lower(),
            wait=True
        ))
        self.blueprint.to_db()

    def final_cleanup(self):
        pass


