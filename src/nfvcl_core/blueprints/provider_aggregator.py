from functools import wraps
from typing import Dict, Optional, List, Any, Tuple, Set, Callable

from nfvcl_core.managers import TopologyManager
from nfvcl_core.utils.blue_utils import get_class_path_str_from_obj
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address
from nfvcl_core_models.network.network_models import PduType, PduModel, MultusInterface
from nfvcl_core_models.providers.providers import BlueprintNGProviderModel, ProviderDataAggregate
from nfvcl_core_models.resources import VmResource, NetResource, VmResourceConfiguration, HelmChartResource, VmStatus
from nfvcl_providers.blueprint.blueprint_provider import BlueprintProvider
from nfvcl_providers.kubernetes.k8s_provider_interface import K8SProviderInterface
from nfvcl_providers.kubernetes.k8s_provider_native import K8SProviderNative
from nfvcl_providers.pdu.pdu_provider import PDUProvider
from nfvcl_providers.virtualization import vim_type_to_provider_mapping
from nfvcl_providers.virtualization.virtualization_provider_interface import VirtualizationProviderInterface


def register_performance(params_to_info=None):
    def decorator(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            provider_aggregator_instance: ProvidersAggregator = args[0]
            info = {}
            if params_to_info:
                for pi in params_to_info:
                    match len(pi):
                        case 2:
                            info[pi[1]] = args[pi[0]] # (1, "blueprint_id")
                        case 3:
                            info[pi[1]] = pi[2](args[pi[0]]) # (1, "vm_name", lambda x: x.name)
                        case 4:
                            info[pi[2]] = pi[3](args[pi[0]], args[pi[1]]) # (0, 3, "vm_name", lambda x, y: x.get_name(y.id))
                        case _:
                            raise ValueError("Invalid number of elements in params_to_info")
            provider_call_id = provider_aggregator_instance.performance_manager.start_provider_call(provider_aggregator_instance.performance_manager.get_pending_operation_id(provider_aggregator_instance.blueprint_id), method.__name__, info)

            res = method(*args, **kwargs)

            provider_aggregator_instance.performance_manager.end_provider_call(provider_call_id)
            return res

        return wrapper

    return decorator


class ProvidersAggregator(VirtualizationProviderInterface, K8SProviderInterface, PDUProvider, BlueprintProvider):
    def init(self):
        pass

    def __init__(self, blueprint_id: str = None, persistence_function: Callable[[], None]=None, topology_manager: TopologyManager = None, blueprint_manager=None, pdu_manager=None, performance_manager=None, vim_clients_manager=None, provider_data_aggregate: ProviderDataAggregate=None):
        super().__init__(-1, blueprint_id, topology_manager, blueprint_manager, pdu_manager=pdu_manager, vim_clients_manager=vim_clients_manager)
        self.persistence_function = persistence_function
        self.performance_manager = performance_manager

        self.virt_providers_impl: Dict[int, VirtualizationProviderInterface] = {}
        self.k8s_providers_impl: Dict[int, K8SProviderInterface] = {}
        self.pdu_provider_impl: Optional[PDUProvider] = None
        self.blueprint_provider_impl: Optional[BlueprintProvider] = None

        # If we need to, we load the data that was saved in the database
        if provider_data_aggregate:
            for area, virt_provider in provider_data_aggregate.virtualization.items():
                provider_data = self.get_virt_provider(int(area)).data.model_validate(virt_provider.provider_data.model_dump())
                self.get_virt_provider(int(area)).data = provider_data

            for area, k8s_provider in provider_data_aggregate.k8s.items():
                provider_data = self.get_k8s_provider(int(area)).data.model_validate(k8s_provider.provider_data.model_dump())
                self.get_k8s_provider(int(area)).data = provider_data

            if provider_data_aggregate.pdu:
                provider_data = self.get_pdu_provider().data.model_validate(provider_data_aggregate.pdu.provider_data.model_dump())
                self.get_pdu_provider().data = provider_data

            if provider_data_aggregate.blueprint:
                provider_data = self.get_blueprint_provider().data.model_validate(provider_data_aggregate.blueprint.provider_data.model_dump())
                self.get_blueprint_provider().data = provider_data

    def get_provider_data_aggregate(self) -> ProviderDataAggregate:
        provider_data_aggregate = ProviderDataAggregate(blueprint_id=self.blueprint_id)
        for area, virt_provider in self.virt_providers_impl.items():
            provider_data_aggregate.virtualization[str(area)] = BlueprintNGProviderModel(
                provider_type=get_class_path_str_from_obj(virt_provider),
                provider_data_type=get_class_path_str_from_obj(virt_provider.data),
                provider_data=virt_provider.data
            )
        for area, k8s_provider in self.k8s_providers_impl.items():
            provider_data_aggregate.k8s[str(area)] = BlueprintNGProviderModel(
                provider_type=get_class_path_str_from_obj(k8s_provider),
                provider_data_type=get_class_path_str_from_obj(k8s_provider.data),
                provider_data=k8s_provider.data
            )
        if self.pdu_provider_impl:
            provider_data_aggregate.pdu = BlueprintNGProviderModel(
                provider_type=get_class_path_str_from_obj(self.pdu_provider_impl),
                provider_data_type=get_class_path_str_from_obj(self.pdu_provider_impl.data),
                provider_data=self.pdu_provider_impl.data
            )
        if self.blueprint_provider_impl:
            provider_data_aggregate.blueprint = BlueprintNGProviderModel(
                provider_type=get_class_path_str_from_obj(self.blueprint_provider_impl),
                provider_data_type=get_class_path_str_from_obj(self.blueprint_provider_impl.data),
                provider_data=self.blueprint_provider_impl.data
            )
        return provider_data_aggregate

    def get_virt_provider(self, area: int):
        vim = self.topology.get_vim_by_area(area)
        if area not in self.virt_providers_impl:
            ProviderClass: type[VirtualizationProviderInterface] = vim_type_to_provider_mapping[vim.vim_type]
            self.virt_providers_impl[area] = ProviderClass(area, self.blueprint_id, topology_manager=self.topology_manager, blueprint_manager=self.blueprint_manager, vim_clients_manager=self.vim_clients_manager, persistence_function=self.persistence_function)
        return self.virt_providers_impl[area]

    def get_k8s_provider(self, area: int):
        if area not in self.k8s_providers_impl:
            self.k8s_providers_impl[area] = K8SProviderNative(area, self.blueprint_id, topology_manager=self.topology_manager, blueprint_manager=self.blueprint_manager, vim_clients_manager=self.vim_clients_manager, persistence_function=self.persistence_function)
        return self.k8s_providers_impl[area]

    def get_pdu_provider(self):
        # The area is -1 because there is only one PDUProvider
        if not self.pdu_provider_impl:
            self.pdu_provider_impl = PDUProvider(area=-1, blueprint_id=self.blueprint_id, topology_manager=self.topology_manager, blueprint_manager=self.blueprint_manager, pdu_manager=self.pdu_manager, vim_clients_manager=self.vim_clients_manager, persistence_function=self.persistence_function)
        return self.pdu_provider_impl

    def get_blueprint_provider(self):
        # The area is -1 because there is only one BlueprintProvider
        if not self.blueprint_provider_impl:
            self.blueprint_provider_impl = BlueprintProvider(area=-1, blueprint_id=self.blueprint_id, topology_manager=self.topology_manager, blueprint_manager=self.blueprint_manager, vim_clients_manager=self.vim_clients_manager, persistence_function=self.persistence_function)
        return self.blueprint_provider_impl

    def get_vim_info(self):
        pass

    @register_performance(params_to_info=[(0, 1, "vim", lambda x, y: x.get_virt_provider(y.area).get_vim_info().name), (1, "vm_name", lambda x: x.name)])
    def create_vm(self, vm_resource: VmResource):
        return self.get_virt_provider(vm_resource.area).create_vm(vm_resource)

    @register_performance(params_to_info=[(0, 1, "vim", lambda x, y: x.get_virt_provider(y.area).get_vim_info().name), (1, "vm_name", lambda x: x.name)])
    def attach_nets(self, vm_resource: VmResource, nets_name: List[str]):
        """
        Attach a network to an already running VM

        Args:
            vm_resource: VM where the network will be attached
            nets_name: List of networks to attach

        Returns:
             the ip that has been set in that network
        """
        return self.get_virt_provider(vm_resource.area).attach_nets(vm_resource, nets_name)

    @register_performance()
    def create_net(self, net_resource: NetResource):
        return self.get_virt_provider(net_resource.area).create_net(net_resource)

    @register_performance(params_to_info=[(0, 1, "vim", lambda x, y: x.get_virt_provider(y.vm_resource.area).get_vim_info().name), (1, "vm_name", lambda x: x.vm_resource.name)])
    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        return self.get_virt_provider(vm_resource_configuration.vm_resource.area).configure_vm(vm_resource_configuration)

    @register_performance(params_to_info=[(0, 1, "vim", lambda x, y: x.get_virt_provider(y.area).get_vim_info().name), (1, "vm_name", lambda x: x.name)])
    def destroy_vm(self, vm_resource: VmResource):
        return self.get_virt_provider(vm_resource.area).destroy_vm(vm_resource)

    def reboot_vm(self, vm_resource: VmResource, hard: bool = False):
        return self.get_virt_provider(vm_resource.area).reboot_vm(vm_resource, hard=hard)

    @register_performance([(1, "vm_resource", lambda x: x.name)])
    def check_vm_status(self, vm_resource: VmResource) -> VmStatus:
        return self.get_virt_provider(vm_resource.area).check_vm_status(vm_resource)

    @register_performance()
    def final_cleanup(self):
        for virt_provider_impl in self.virt_providers_impl.values():
            virt_provider_impl.final_cleanup()
        for k8s_provider_impl in self.k8s_providers_impl.values():
            k8s_provider_impl.final_cleanup()
        self.get_pdu_provider().final_cleanup()
        self.get_blueprint_provider().final_cleanup()

    @register_performance(params_to_info=[(1, "release_name", lambda x: x.name)])
    def install_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        return self.get_k8s_provider(helm_chart_resource.area).install_helm_chart(helm_chart_resource, values)

    @register_performance(params_to_info=[(1, "release_name", lambda x: x.name)])
    def update_values_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        return self.get_k8s_provider(helm_chart_resource.area).update_values_helm_chart(helm_chart_resource, values)

    @register_performance(params_to_info=[(1, "release_name", lambda x: x.name)])
    def uninstall_helm_chart(self, helm_chart_resource: HelmChartResource):
        return self.get_k8s_provider(helm_chart_resource.area).uninstall_helm_chart(helm_chart_resource)

    @register_performance()
    def get_pod_log(self, helm_chart_resource: HelmChartResource, pod_name: str, tail_lines: Optional[int] = None) -> str:
        return self.get_k8s_provider(helm_chart_resource.area).get_pod_log(helm_chart_resource, pod_name, tail_lines)

    def reserve_k8s_multus_ip(self, area: int, network_name: str) -> MultusInterface:
        return self.get_k8s_provider(area).reserve_k8s_multus_ip(area, network_name)

    def release_k8s_multus_ip(self, area: int, network_name: str, ip_address: SerializableIPv4Address) -> MultusInterface:
        return self.get_k8s_provider(area).release_k8s_multus_ip(area, network_name, ip_address)

    def find_pdu(self, area: int, pdu_type: PduType, instance_type: Optional[str] = None, name: Optional[str] = None) -> PduModel:
        return self.get_pdu_provider().find_pdu(area, pdu_type, instance_type=instance_type, name=name)

    def find_pdus(self, area: int, pdu_type: PduType, instance_type: Optional[str] = None) -> List[PduModel]:
        return self.get_pdu_provider().find_pdus(area, pdu_type, instance_type)

    def is_pdu_locked(self, pdu_model: PduModel) -> bool:
        return self.get_pdu_provider().is_pdu_locked(pdu_model)

    def is_pdu_locked_by_current_blueprint(self, pdu_model: PduModel) -> bool:
        return self.get_pdu_provider().is_pdu_locked_by_current_blueprint(pdu_model)

    def lock_pdu(self, pdu_model: PduModel) -> PduModel:
        return self.get_pdu_provider().lock_pdu(pdu_model)

    def unlock_pdu(self, pdu_model: PduModel) -> PduModel:
        return self.get_pdu_provider().unlock_pdu(pdu_model)

    def get_pdu_configurator(self, pdu_model: PduModel) -> Any:
        return self.get_pdu_provider().get_pdu_configurator(pdu_model)

    def check_networks(self, area: int, networks_to_check: set[str]) -> Tuple[bool, Set[str]]:
        return self.get_virt_provider(area).check_networks(area, networks_to_check)

    @register_performance(params_to_info=[(1, "blueprint_type")])
    def create_blueprint(self, path: str, msg: Any):
        return self.get_blueprint_provider().create_blueprint(path, msg)

    @register_performance(params_to_info=[(1, "blueprint_id")])
    def delete_blueprint(self, blueprint_id: str):
        return self.get_blueprint_provider().delete_blueprint(blueprint_id)

    @register_performance(params_to_info=[(1, "blueprint_id"), (2, "function_name")])
    def call_blueprint_function(self, blue_id: str, function_name: str, *args, **kwargs) -> Any:
        return self.get_blueprint_provider().call_blueprint_function(blue_id, function_name, *args, **kwargs)

    @register_performance()
    def restart_deployment(self, helm_chart_resource: HelmChartResource, deployment_name: str):
        return self.get_k8s_provider(helm_chart_resource.area).restart_deployment(helm_chart_resource, deployment_name)

    @register_performance()
    def restart_all_deployments(self, helm_chart_resource: HelmChartResource, namespace: str):
        return self.get_k8s_provider(helm_chart_resource.area).restart_all_deployments(helm_chart_resource, namespace)

    @register_performance()
    def exec_command_in_pod(self, helm_chart_resource: HelmChartResource, command: List[str], pod_name=None, container_name=None):
        return self.get_k8s_provider(helm_chart_resource.area).exec_command_in_pod(helm_chart_resource, command, pod_name, container_name)
