from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple

from nfvcl_common.utils.log import blueprint_log_context, create_logger
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address
from nfvcl_core_models.network.network_models import (
    MultusInterface,
    PduLockType,
    PduModel,
    PduType,
)
from nfvcl_core_models.resources import (
    HelmChartResource,
    NetResource,
    VmResource,
    VmResourceConfiguration,
    VmStatus,
)

if TYPE_CHECKING:
    from nfvcl_core.managers.blueprint_manager import BlueprintManager
    from nfvcl_core.managers.performance_manager import PerformanceManager
    from nfvcl_core.managers.provider_manager import ProviderManager
    from nfvcl_core.managers.topology_manager import TopologyManager
    from nfvcl_providers.blueprint.blueprint_provider import BlueprintProvider
    from nfvcl_providers.diagnostic.diagnostic_provider import DiagnosticProvider
    from nfvcl_providers.kubernetes.k8s_provider_interface import K8SProviderInterface
    from nfvcl_providers.pdu.pdu_provider import PDUProvider
    from nfvcl_providers.virtualization.virtualization_provider_interface import (
        VirtualizationProviderInterface,
    )


def add_blueprint_log_context():
    def decorator(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            provider_aggregator_instance: ProvidersAggregator = args[0]
            blueprint_id = provider_aggregator_instance.blueprint_id
            with blueprint_log_context(blueprint_id):
                return method(*args, **kwargs)

        return wrapper

    return decorator

def register_performance(params_to_info=None):
    def decorator(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            provider_aggregator_instance: ProvidersAggregator = args[0]
            provider_call_id = None
            if provider_aggregator_instance.performance_manager is not None:
                info = {}
                if params_to_info:
                    for pi in params_to_info:
                        match len(pi):
                            case 2:
                                info[pi[1]] = args[pi[0]]
                            case 3:
                                info[pi[1]] = pi[2](args[pi[0]])
                            case 4:
                                info[pi[2]] = pi[3](args[pi[0]], args[pi[1]])
                            case _:
                                raise ValueError("Invalid number of elements in params_to_info")
                provider_call_id = provider_aggregator_instance.performance_manager.start_provider_call_for_blueprint(
                    provider_aggregator_instance.blueprint_id,
                    method.__name__,
                    info,
                )

            try:
                return method(*args, **kwargs)
            except Exception as exc:
                raise exc
            finally:
                if provider_call_id is not None:
                    provider_aggregator_instance.performance_manager.end_provider_call(provider_call_id)
        return wrapper
    return decorator


class ProvidersAggregator:
    def __init__(
        self,
        blueprint_id: str,
        persistence_function: Callable[[], None],
        provider_manager: ProviderManager,
        topology_manager: TopologyManager,
        blueprint_manager: BlueprintManager,
        performance_manager: PerformanceManager | None = None,
    ):
        self.blueprint_id = blueprint_id
        self.topology_manager = topology_manager
        self.blueprint_manager = blueprint_manager
        self.provider_manager = provider_manager
        # The persistence function is never called at the moment, not sure that's still needed
        self.persistence_function = persistence_function
        self.performance_manager = performance_manager
        self.logger = create_logger(self.__class__.__name__)

        self._virt_provider_areas: Set[int] = set()

    def _get_virt_provider(self, area: int) -> VirtualizationProviderInterface:
        self._virt_provider_areas.add(area)
        return self.provider_manager.get_virtualization_provider_for_area(area)

    def _get_k8s_provider(self, area: int) -> K8SProviderInterface:
        return self.provider_manager.get_kubernetes_provider(area)

    def _get_pdu_provider(self) -> PDUProvider:
        return self.provider_manager.get_pdu_provider()

    def _get_blueprint_provider(self) -> BlueprintProvider:
        return self.provider_manager.get_blueprint_provider()

    def _get_diagnostic_provider(self) -> DiagnosticProvider:
        return self.provider_manager.get_diagnostic_provider()

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(0, 1, "vim", lambda x, y: x._get_virt_provider(y.area).get_vim_info(y.area).name), (1, "vm_name", lambda x: x.name)])
    def create_vm(self, vm_resource: VmResource):
        return self._get_virt_provider(vm_resource.area).create_vm(vm_resource)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(0, 1, "vim", lambda x, y: x._get_virt_provider(y.area).get_vim_info(y.area).name), (1, "vm_name", lambda x: x.name)])
    def attach_nets(self, vm_resource: VmResource, nets_name: List[str]):
        """
        Attach a network to an already running VM.

        Args:
            vm_resource: VM where the network will be attached
            nets_name: List of networks to attach

        Returns:
             the ip that has been set in that network
        """
        return self._get_virt_provider(vm_resource.area).attach_nets(vm_resource, nets_name)

    @add_blueprint_log_context()
    @register_performance()
    def create_net(self, net_resource: NetResource):
        return self._get_virt_provider(net_resource.area).create_net(net_resource)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(0, 1, "vim", lambda x, y: x._get_virt_provider(y.vm_resource.area).get_vim_info(y.vm_resource.area).name), (1, "vm_name", lambda x: x.vm_resource.name)])
    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        return self._get_virt_provider(vm_resource_configuration.vm_resource.area).configure_vm(vm_resource_configuration)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(0, 1, "vim", lambda x, y: x._get_virt_provider(y.area).get_vim_info(y.area).name), (1, "vm_name", lambda x: x.name)])
    def destroy_vm(self, vm_resource: VmResource):
        return self._get_virt_provider(vm_resource.area).destroy_vm(vm_resource)

    @add_blueprint_log_context()
    def reboot_vm(self, vm_resource: VmResource, hard: bool = False):
        return self._get_virt_provider(vm_resource.area).reboot_vm(vm_resource, hard=hard)

    @add_blueprint_log_context()
    @register_performance([(1, "vm_resource", lambda x: x.name)])
    def check_vm_status(self, vm_resource: VmResource) -> VmStatus:
        return self._get_virt_provider(vm_resource.area).check_vm_status(vm_resource)

    @add_blueprint_log_context()
    @register_performance()
    def final_cleanup(self):
        virt_providers: List[VirtualizationProviderInterface] = []
        for area in self._virt_provider_areas:
            virt_provider = self._get_virt_provider(area)
            if virt_provider not in virt_providers:
                virt_providers.append(virt_provider)

        if virt_providers:
            for virt_provider in virt_providers:
                virt_provider.cleanup_resource_group(self.blueprint_id)
        else:
            for virt_provider in self.provider_manager.get_virtualization_providers():
                try:
                    virt_provider.cleanup_resource_group(self.blueprint_id)
                except ValueError as exc:
                    self.logger.debug(
                        f"Skipping area-less final cleanup for {virt_provider.__class__.__name__}: {exc}"
                    )

        self.provider_manager.get_kubernetes_provider().cleanup_resource_group(self.blueprint_id)
        self._get_pdu_provider().cleanup_resource_group(self.blueprint_id)
        self._get_blueprint_provider().cleanup_resource_group(self.blueprint_id)
        self._get_diagnostic_provider().cleanup_resource_group(self.blueprint_id)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "release_name", lambda x: x.name)])
    def install_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        return self._get_k8s_provider(helm_chart_resource.area).install_helm_chart(helm_chart_resource, values)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "release_name", lambda x: x.name)])
    def update_values_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        return self._get_k8s_provider(helm_chart_resource.area).update_values_helm_chart(helm_chart_resource, values)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "release_name", lambda x: x.name)])
    def uninstall_helm_chart(self, helm_chart_resource: HelmChartResource):
        return self._get_k8s_provider(helm_chart_resource.area).uninstall_helm_chart(helm_chart_resource)

    @add_blueprint_log_context()
    @register_performance()
    def get_pod_log(self, helm_chart_resource: HelmChartResource, pod_name: str, tail_lines: Optional[int] = None) -> str:
        return self._get_k8s_provider(helm_chart_resource.area).get_pod_log(helm_chart_resource, pod_name, tail_lines)

    @add_blueprint_log_context()
    def reserve_k8s_multus_ip(self, area: int, network_name: str) -> MultusInterface:
        return self._get_k8s_provider(area).reserve_k8s_multus_ip(area, self.blueprint_id, network_name)

    @add_blueprint_log_context()
    def release_k8s_multus_ip(self, area: int, network_name: str, ip_address: SerializableIPv4Address) -> MultusInterface:
        return self._get_k8s_provider(area).release_k8s_multus_ip(
            area,
            self.blueprint_id,
            network_name,
            ip_address,
        )

    @add_blueprint_log_context()
    def add_pdu(self, pdu: PduModel) -> PduModel:
        return self._get_pdu_provider().add_pdu(pdu)

    @add_blueprint_log_context()
    def delete_pdu(self, pdu_id: str) -> None:
        return self._get_pdu_provider().delete_pdu(pdu_id)

    @add_blueprint_log_context()
    def find_pdu(self, area: int, pdu_type: PduType, instance_type: Optional[str] = None, name: Optional[str] = None) -> PduModel:
        return self._get_pdu_provider().find_pdu(area, pdu_type, instance_type=instance_type, name=name)

    @add_blueprint_log_context()
    def find_pdus(self, area: int, pdu_type: PduType, instance_type: Optional[str] = None) -> List[PduModel]:
        return self._get_pdu_provider().find_pdus(area, pdu_type, instance_type)

    @add_blueprint_log_context()
    def is_pdu_locked(self, pdu_model: PduModel, lock_type: PduLockType) -> bool:
        return self._get_pdu_provider().is_pdu_locked(pdu_model, lock_type)

    @add_blueprint_log_context()
    def is_pdu_locked_by_current_blueprint(self, pdu_model: PduModel, lock_type: PduLockType) -> bool:
        return self._get_pdu_provider().is_pdu_locked_by_blueprint(pdu_model, lock_type, self.blueprint_id)

    @add_blueprint_log_context()
    def lock_pdu(self, pdu_model: PduModel, lock_type: PduLockType) -> PduModel:
        return self._get_pdu_provider().lock_pdu(pdu_model, lock_type, self.blueprint_id)

    @add_blueprint_log_context()
    def unlock_pdu(self, pdu_model: PduModel, lock_type: PduLockType) -> PduModel:
        return self._get_pdu_provider().unlock_pdu(pdu_model, lock_type, self.blueprint_id)

    @add_blueprint_log_context()
    def get_pdu_configurator(self, pdu_model: PduModel, lock_type: PduLockType) -> Any:
        return self._get_pdu_provider().get_pdu_configurator(pdu_model, lock_type, self.blueprint_id)

    @add_blueprint_log_context()
    def check_networks_exist_on_vim(self, area: int, networks_to_check: set[str]) -> Tuple[bool, Set[str]]:
        return self._get_virt_provider(area).check_networks_exist_on_vim(area, networks_to_check)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "blueprint_type")])
    def create_blueprint(self, path: str, msg: Any):
        return self._get_blueprint_provider().create_blueprint(path, msg, self.blueprint_id)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "blueprint_id")])
    def delete_blueprint(self, blueprint_id: str):
        return self._get_blueprint_provider().delete_blueprint(blueprint_id, self.blueprint_id)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "blueprint_id"), (2, "function_name")])
    def call_blueprint_function(self, blue_id: str, function_name: str, *args, **kwargs) -> Any:
        return self._get_blueprint_provider().call_blueprint_function(blue_id, function_name, *args, **kwargs)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "vm_name", lambda x: x.name)])
    def install_rpcapd(self, vm_resource: VmResource, download_url: str = "https://images.tnt-lab.unige.it/private/rpcapd"):
        return self._get_diagnostic_provider().install_rpcapd(vm_resource, download_url)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "vm_name", lambda x: x.name)])
    def uninstall_rpcapd(self, vm_resource: VmResource):
        return self._get_diagnostic_provider().uninstall_rpcapd(vm_resource)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "vm_name", lambda x: x.name)])
    def start_rpcapd(self, vm_resource: VmResource):
        return self._get_diagnostic_provider().start_rpcapd(vm_resource)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "vm_name", lambda x: x.name)])
    def stop_rpcapd(self, vm_resource: VmResource):
        return self._get_diagnostic_provider().stop_rpcapd(vm_resource)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "vm_name", lambda x: x.name)])
    def restart_rpcapd(self, vm_resource: VmResource):
        return self._get_diagnostic_provider().restart_rpcapd(vm_resource)

    @add_blueprint_log_context()
    @register_performance(params_to_info=[(1, "vm_name", lambda x: x.name)])
    def get_rpcapd_status(self, vm_resource: VmResource):
        return self._get_diagnostic_provider().get_rpcapd_status(vm_resource)

    @add_blueprint_log_context()
    @register_performance()
    def restart_deployment(self, helm_chart_resource: HelmChartResource, deployment_name: str):
        return self._get_k8s_provider(helm_chart_resource.area).restart_deployment(helm_chart_resource, deployment_name)

    @add_blueprint_log_context()
    @register_performance()
    def restart_all_deployments(self, helm_chart_resource: HelmChartResource, namespace: str):
        return self._get_k8s_provider(helm_chart_resource.area).restart_all_deployments(helm_chart_resource, namespace)

    @add_blueprint_log_context()
    @register_performance()
    def exec_command_in_pod(self, helm_chart_resource: HelmChartResource, command: List[str], pod_name=None, container_name=None):
        return self._get_k8s_provider(helm_chart_resource.area).exec_command_in_pod(helm_chart_resource, command, pod_name, container_name)

    @add_blueprint_log_context()
    @register_performance()
    def spawn_ephemeral_container_in_pod(
        self,
        helm_chart_resource: HelmChartResource,
        pod_name: str,
        container_name: str,
        image: str,
        command: List[str],
        args: Optional[List[str]] = None,
        env: Optional[dict] = None,
        wait_for_completion: bool = True,
        timeout: int = 120,
    ):
        return self._get_k8s_provider(helm_chart_resource.area).spawn_ephemeral_container_in_pod(
            helm_chart_resource,
            pod_name,
            container_name,
            image,
            command,
            args,
            env,
            wait_for_completion,
            timeout,
        )

    @add_blueprint_log_context()
    @register_performance()
    def spawn_pod(
        self,
        helm_chart_resource: HelmChartResource,
        pod_name: str,
        image: str,
        command: List[str],
        args: Optional[List[str]] = None,
        env: Optional[dict] = None,
        wait_for_completion: bool = True,
        timeout: int = 120,
    ) -> str:
        return self._get_k8s_provider(helm_chart_resource.area).spawn_pod(
            helm_chart_resource,
            pod_name,
            image,
            command,
            args,
            env,
            wait_for_completion,
            timeout,
        )

    @add_blueprint_log_context()
    def check_lb_available(self, area: int, necessary_ip: int) -> bool:
        return self._get_k8s_provider(area).check_lb_available(area, necessary_ip)
