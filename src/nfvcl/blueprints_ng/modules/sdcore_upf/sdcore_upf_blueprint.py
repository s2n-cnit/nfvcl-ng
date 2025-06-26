from __future__ import annotations

from typing import Optional, List, Dict, Literal

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf_vm import Generic5GUPFVMBlueprintNGState, Generic5GUPFVMBlueprintNG
from nfvcl_core.blueprints.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import DeployedUPFInfo
from nfvcl_core_models.http_models import HttpRequestType
from nfvcl_core_models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address
from nfvcl_core_models.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo, Slice5GWithDNNs
from nfvcl_core.utils.blue_utils import rel_path

SDCORE_UPF_BLUE_TYPE = "sdcore_upf"


class SdCoreUPFBlueprintNGState(Generic5GUPFVMBlueprintNGState):
    vm_configurators: Dict[str, SDCoreUPFConfigurator] = Field(default_factory=dict)
    currently_deployed_dnns: Dict[str, DeployedUPFInfo] = Field(default_factory=dict)

class SDCoreUPFConfiguration(NFVCLBaseModel):
    upf_mode: str = Field()

    n3_nic_name: str = Field()
    n6_nic_name: str = Field()

    n3_net_cidr: str = Field()
    n6_net_cidr: str = Field()

    n3_nic_mac: str = Field()
    n6_nic_mac: str = Field()

    n3_nh_ip: str = Field()
    n6_nh_ip: str = Field()

    n3_route: str = Field()
    n6_route: str = Field()

    start: bool = Field()

    dnn: str = Field()
    ue_ip_pool_cidr: str = Field()


class SDCoreUPFGreenQueueConfiguration(NFVCLBaseModel):
    module_class: Literal['GreenQueueBypass', 'GreenBypass'] = Field(default="GreenQueueBypass")
    dnn: str = Field()
    src_mac: str = Field()
    dst_mac: str = Field()
    src_ip: str = Field()
    dst_ip: str = Field()
    ip_ttl: int = Field()
    src_port: int = Field()
    dst_port: int = Field()
    sleep_ms: int = Field()
    enable_bypass: bool = Field()
    release_single_packet: bool = Field()

class SDCoreUPFGreenQueueIPConfiguration(NFVCLBaseModel):
    dnn: str = Field()
    ip: str = Field()

class SDCoreUPFGreenQueueRemoveConfiguration(NFVCLBaseModel):
    dnn: str = Field()


class SDCoreUPFConfigurator(VmResourceAnsibleConfiguration):
    configuration: Optional[SDCoreUPFConfiguration] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook SDCoreUPFConfigurator")

        upf_config_path = "/opt/upf/upf.jsonc"
        run_upf_config_path = "/opt/upf/run_upf.env"

        # Get the n3 and n6 gateways mac addresses using ARP
        ansible_builder.add_run_command_and_gather_output_tasks(f"sudo arping -r -c 1 -I {self.configuration.n3_nic_name} {self.configuration.n3_nh_ip}", "n3_nh_mac")
        ansible_builder.add_run_command_and_gather_output_tasks(f"sudo arping -r -c 1 -I {self.configuration.n6_nic_name} {self.configuration.n6_nh_ip}", "n6_nh_mac")

        ansible_builder.add_template_task(rel_path("config/upf.jsonc.jinja2"), upf_config_path)
        ansible_builder.add_template_task(rel_path("config/run_upf.env.jinja2"), run_upf_config_path)

        ansible_builder.set_vars_from_fields(self.configuration)

        if self.configuration.start:
            ansible_builder.add_service_task("sdcore-upf", ServiceState.RESTARTED, True)

        return ansible_builder.build()

class SDCoreUPFGreenQueueConfigurator(VmResourceAnsibleConfiguration):
    configuration: Optional[SDCoreUPFGreenQueueConfiguration] = Field(default=None)
    n6_nic_name: str = Field()

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook SDCoreUPFGreenQueueConfigurator")
        ansible_builder.add_tasks_from_file(rel_path("config/green_queue_setup.yaml"))

        ansible_builder.set_vars_from_fields(self.configuration)
        ansible_builder.set_var("n6_nic_name", self.n6_nic_name)

        return ansible_builder.build()

class SDCoreUPFGreenQueueAddIPConfigurator(VmResourceAnsibleConfiguration):
    configuration: Optional[SDCoreUPFGreenQueueIPConfiguration] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook SDCoreUPFGreenQueueAddIPConfigurator")
        ansible_builder.add_tasks_from_file(rel_path("config/green_queue_add_ip.yaml"))

        ansible_builder.set_vars_from_fields(self.configuration)

        return ansible_builder.build()


class SDCoreUPFGreenQueueReleaseIPConfigurator(VmResourceAnsibleConfiguration):
    configuration: Optional[SDCoreUPFGreenQueueIPConfiguration] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook SDCoreUPFGreenQueueReleaseIPConfigurator")
        ansible_builder.add_tasks_from_file(rel_path("config/green_queue_release.yaml"))

        ansible_builder.set_vars_from_fields(self.configuration)

        return ansible_builder.build()

class SDCoreUPFGreenQueueRemoveConfigurator(VmResourceAnsibleConfiguration):
    n6_nic_name: str = Field()

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook SDCoreUPFGreenQueueRemoveConfigurator")
        ansible_builder.add_tasks_from_file(rel_path("config/green_queue_remove.yaml"))

        ansible_builder.set_var("n6_nic_name", self.n6_nic_name)

        return ansible_builder.build()

UPF_IMAGE_NAME = "sd-core-upf-v2.0.2-s2n-6"
UPF_IMAGE_URL = "https://images.tnt-lab.unige.it/sd-core-upf/sd-core-upf-v2.0.2-s2n-6-ubuntu2404.qcow2"


@blueprint_type(SDCORE_UPF_BLUE_TYPE)
class SdCoreUPFBlueprintNG(Generic5GUPFVMBlueprintNG[SdCoreUPFBlueprintNGState, UPFBlueCreateModel]):
    router_needed = True

    sdcore_upf_image = VmResourceImage(name=UPF_IMAGE_NAME, url=UPF_IMAGE_URL)
    sdcore_upf_flavor = VmResourceFlavor(vcpu_count='4', memory_mb='8192', storage_gb='10')

    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFVMBlueprintNGState] = SdCoreUPFBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_upf(self):
        self.logger.info("Starting creation of SdCoreBlueprintNG blueprint")
        self.update_deployments()

    def update_upf(self):
        self.logger.debug("SdCoreBlueprintNG update")
        self.update_deployments()

    def update_deployments(self):
        dnns_to_deploy: List[str] = []
        for slice in self.state.current_config.slices:
            for dnnslice in slice.dnn_list:
                dnns_to_deploy.append(dnnslice.dnn)
        for dnn in set(dnns_to_deploy):
            if dnn not in self.state.currently_deployed_dnns:
                deployed_info = self.deploy_upf_vm(dnn)
                self.state.upf_list.append(deployed_info)
                self.state.currently_deployed_dnns[dnn] = deployed_info
        dnn_to_undeploy = set(self.state.currently_deployed_dnns) - set(dnns_to_deploy)
        for dnn in set(dnn_to_undeploy):
            deployed_info = self.undeploy_upf_vm(dnn)
            self.state.upf_list.remove(deployed_info)
            del self.state.currently_deployed_dnns[dnn]

    def deploy_upf_vm(self, dnn: str) -> DeployedUPFInfo:
        upf_vm = VmResource(
            area=self.state.current_config.area_id,
            name=f"{self.id}_{self.state.current_config.area_id}_SDCORE_UPF_{dnn}",
            image=self.sdcore_upf_image,
            flavor=self.sdcore_upf_flavor,
            username="ubuntu",
            password="ubuntu",
            management_network=self.state.current_config.networks.mgt.net_name,
            additional_networks=[self.state.current_config.networks.n4.net_name, self.state.current_config.networks.n3.net_name, self.state.current_config.networks.n6.net_name],
            require_port_security_disabled=True
        )
        self.register_resource(upf_vm)
        self.provider.create_vm(upf_vm)

        upf_vm_configurator = SDCoreUPFConfigurator(vm_resource=upf_vm, configuration=SDCoreUPFConfiguration(
            upf_mode="dpdk",
            n3_nic_name=upf_vm.network_interfaces[self.state.current_config.networks.n3.net_name][0].fixed.interface_name,
            n6_nic_name=upf_vm.network_interfaces[self.state.current_config.networks.n6.net_name][0].fixed.interface_name,
            n3_net_cidr=upf_vm.network_interfaces[self.state.current_config.networks.n3.net_name][0].fixed.get_ip_prefix(),
            n6_net_cidr=upf_vm.network_interfaces[self.state.current_config.networks.n6.net_name][0].fixed.get_ip_prefix(),
            n3_nic_mac=upf_vm.network_interfaces[self.state.current_config.networks.n3.net_name][0].fixed.mac,
            n6_nic_mac=upf_vm.network_interfaces[self.state.current_config.networks.n6.net_name][0].fixed.mac,
            n3_nh_ip=self.state.current_config.n3_gateway_ip.exploded,
            n6_nh_ip=self.state.current_config.n6_gateway_ip.exploded,
            n3_route=self.state.current_config.gnb_cidr.exploded,
            n6_route="0.0.0.0/0",
            start=self.state.current_config.start,
            dnn=dnn,
            ue_ip_pool_cidr=self.get_dnn_ip_pool(dnn)
        ))
        self.register_resource(upf_vm_configurator)
        self.provider.configure_vm(upf_vm_configurator)

        self.state.vm_resources[upf_vm.id] = upf_vm
        self.state.vm_configurators[upf_vm_configurator.id] = upf_vm_configurator

        return DeployedUPFInfo(
            area=self.state.current_config.area_id,
            served_slices=self.get_slices_for_dnn(dnn),
            vm_resource_id=upf_vm.id,
            vm_configurator_id=upf_vm_configurator.id,
            network_info=UPFNetworkInfo(
                n4_cidr=SerializableIPv4Network(upf_vm.network_interfaces[self.create_config.networks.n4.net_name][0].fixed.cidr),
                n3_cidr=SerializableIPv4Network(upf_vm.network_interfaces[self.create_config.networks.n3.net_name][0].fixed.cidr),
                n6_cidr=SerializableIPv4Network(upf_vm.network_interfaces[self.create_config.networks.n6.net_name][0].fixed.cidr),
                n4_ip=SerializableIPv4Address(upf_vm.network_interfaces[self.create_config.networks.n4.net_name][0].fixed.ip),
                n3_ip=SerializableIPv4Address(upf_vm.network_interfaces[self.create_config.networks.n3.net_name][0].fixed.ip),
                n6_ip=SerializableIPv4Address(upf_vm.network_interfaces[self.create_config.networks.n6.net_name][0].fixed.ip)
            )
        )

    def undeploy_upf_vm(self, dnn: str):
        upf_info = self.state.currently_deployed_dnns[dnn]

        self.provider.destroy_vm(self.state.vm_resources[upf_info.vm_resource_id])

        self.deregister_resource_by_id(upf_info.vm_resource_id)
        self.deregister_resource_by_id(upf_info.vm_configurator_id)
        del self.state.vm_resources[upf_info.vm_resource_id]
        del self.state.vm_configurators[upf_info.vm_configurator_id]

        return upf_info

    @day2_function("/green_queue_setup", [HttpRequestType.PUT])
    def green_queue_setup(self, model: SDCoreUPFGreenQueueConfiguration):
        upf_info = self.state.currently_deployed_dnns[model.dnn]
        upf_vm = self.state.vm_resources[upf_info.vm_resource_id]
        green_configurator = SDCoreUPFGreenQueueConfigurator(
            vm_resource=upf_vm,
            n6_nic_name=upf_vm.network_interfaces[self.state.current_config.networks.n6.net_name][0].fixed.interface_name,
            configuration=model
        )
        self.provider.configure_vm(green_configurator)

    @day2_function("/green_queue_remove", [HttpRequestType.PUT])
    def green_queue_remove(self, model: SDCoreUPFGreenQueueRemoveConfiguration):
        upf_info = self.state.currently_deployed_dnns[model.dnn]
        upf_vm = self.state.vm_resources[upf_info.vm_resource_id]
        green_configurator = SDCoreUPFGreenQueueRemoveConfigurator(
            vm_resource=upf_vm,
            n6_nic_name=upf_vm.network_interfaces[self.state.current_config.networks.n6.net_name][0].fixed.interface_name
        )
        self.provider.configure_vm(green_configurator)

    @day2_function("/green_queue_add_ip", [HttpRequestType.PUT])
    def green_queue_add_ip(self, model: SDCoreUPFGreenQueueIPConfiguration):
        upf_info = self.state.currently_deployed_dnns[model.dnn]
        upf_vm = self.state.vm_resources[upf_info.vm_resource_id]
        green_configurator = SDCoreUPFGreenQueueAddIPConfigurator(
            vm_resource=upf_vm,
            configuration=model
        )
        self.provider.configure_vm(green_configurator)

    @day2_function("/green_queue_release_ip", [HttpRequestType.PUT])
    def green_queue_release_ip(self, model: SDCoreUPFGreenQueueIPConfiguration):
        upf_info = self.state.currently_deployed_dnns[model.dnn]
        upf_vm = self.state.vm_resources[upf_info.vm_resource_id]
        green_configurator = SDCoreUPFGreenQueueReleaseIPConfigurator(
            vm_resource=upf_vm,
            configuration=model
        )
        self.provider.configure_vm(green_configurator)
