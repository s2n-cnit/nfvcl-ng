import abc
from typing import Any, Dict, Optional, List, Callable

from nfvcl_core.managers.topology_manager import TopologyManager
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address

from nfvcl_core_models.network.network_models import MultusInterface
from nfvcl_core_models.providers.providers import ProviderData
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_providers.provider_interface import ProviderInterface


class K8SProviderData(ProviderData):
    pass


class K8SProviderException(Exception):
    pass


class K8SProviderInterface(ProviderInterface):
    data: K8SProviderData

    def __init__(self, topology_manager: TopologyManager, persistence_function: Optional[Callable] = None):
        self.topology_manager = topology_manager
        super().__init__(persistence_function)

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
    def get_pod_log(self, helm_chart_resource: HelmChartResource, pod_name: str, tail_lines: Optional[int] = None) -> str:
        pass

    @abc.abstractmethod
    def reserve_k8s_multus_ip(self, area: int, resource_group_id: str, network_name: str) -> MultusInterface:
        pass

    @abc.abstractmethod
    def release_k8s_multus_ip(self, area: int, resource_group_id: str, network_name: str, ip_address: SerializableIPv4Address) -> MultusInterface:
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

    @abc.abstractmethod
    def spawn_ephemeral_container_in_pod(self, helm_chart_resource: HelmChartResource, pod_name: str, container_name: str, image: str, command: List[str], args: Optional[List[str]] = None, env: Optional[dict] = None, wait_for_completion: bool = True, timeout: int = 120):
        pass

    @abc.abstractmethod
    def spawn_pod(self, helm_chart_resource: HelmChartResource, pod_name: str, image: str, command: List[str], args: Optional[List[str]] = None, env: Optional[dict] = None, wait_for_completion: bool = True, timeout: int = 120) -> str:
        pass

    @abc.abstractmethod
    def check_lb_available(self, area: int, necessary_ip: int) -> bool:
        pass
