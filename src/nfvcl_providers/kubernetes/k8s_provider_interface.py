import abc
from typing import Any, Dict, Optional, List, Callable

from nfvcl_core.managers.topology_manager import TopologyManager
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address

from nfvcl_core_models.network.network_models import MultusInterface
from nfvcl_providers.blueprint_ng_provider_interface import BlueprintNGProviderData, \
    BlueprintNGProviderInterface
from nfvcl_core_models.resources import HelmChartResource


class K8SProviderData(BlueprintNGProviderData):
    pass


class K8SProviderException(Exception):
    pass


class K8SProviderInterface(BlueprintNGProviderInterface):
    data: K8SProviderData

    def __init__(self, area: int, blueprint_id: str, topology_manager: TopologyManager, persistence_function: Optional[Callable] = None):
        self.topology_manager = topology_manager
        super().__init__(area, blueprint_id, persistence_function)

    @abc.abstractmethod
    def install_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        pass

    @abc.abstractmethod
    def update_values_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        pass

    @abc.abstractmethod
    def uninstall_helm_chart(self, helm_chart_resource: HelmChartResource):
        pass

    @abc.abstractmethod
    def get_pod_log(self, helm_chart_resource: HelmChartResource, pod_name: str, tail_lines: Optional[int]=None) -> str:
        pass

    @abc.abstractmethod
    def reserve_k8s_multus_ip(self, area: int, network_name: str) -> MultusInterface:
        pass

    @abc.abstractmethod
    def release_k8s_multus_ip(self, area: int, network_name: str, ip_address: SerializableIPv4Address) -> MultusInterface:
        pass

    @abc.abstractmethod
    def restart_deployment(self, helm_chart_resource: HelmChartResource, deployment_name: str):
        pass

    @abc.abstractmethod
    def restart_all_deployments(self, helm_chart_resource: HelmChartResource, namespace: str):
        pass

    @abc.abstractmethod
    def exec_command_in_pod(self, helm_chart_resource: HelmChartResource, command: List[str], pod_name: str, container_name=None):
        pass
