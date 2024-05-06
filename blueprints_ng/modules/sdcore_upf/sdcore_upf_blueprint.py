from __future__ import annotations

import copy
from typing import Optional

from pydantic import Field
from starlette.requests import Request

from blueprints_ng.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration
from blueprints_ng.utils import rel_path
from models.base_model import NFVCLBaseModel
from models.blueprint_ng.g5.ueransim import GNBN3Info
from models.blueprint_ng.g5.upf import UPFBlueCreateModel

SDCORE_UPF_BLUE_TYPE = "sdcore_upf"


class SdCoreUPFCreateModel(UPFBlueCreateModel):
    gnb_n3_ip: str = Field()
    gnb_n3_mac: str = Field()
    dnn: str = Field()
    ue_ip_pool_cidr: str = Field()
    start: Optional[bool] = Field(default=True)


class SdCoreUPFBlueprintNGState(BlueprintNGState):
    upf_vm: Optional[VmResource] = Field(default=None)
    upf_vm_configurator: Optional[SDCoreUPFConfigurator] = Field(default=None)

    n3_router_vm: Optional[VmResource] = Field(default=None)
    n3_router_vm_configurator: Optional[N3RouterConfigurator] = Field(default=None)

    n6_router_vm: Optional[VmResource] = Field(default=None)
    n6_router_vm_configurator: Optional[N6RouterConfigurator] = Field(default=None)


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

    n3_nh_mac: str = Field()
    n6_nh_mac: str = Field()

    n3_route: str = Field()
    n6_route: str = Field()

    start: bool = Field()

    dnn: str = Field()
    ue_ip_pool_cidr: str = Field()


class N3RouterConfigurator(VmResourceAnsibleConfiguration):
    n3_net_name: str = Field()
    gnb_net_name: str = Field()
    gnb_ip: str = Field()
    ue_ip_pool_cidr: str = Field()

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder(f"Playbook N3RouterConfigurator")
        # ansible_builder.add_shell_task("echo 1 > /proc/sys/net/ipv4/ip_forward")
        # ansible_builder.add_shell_task(f"ethtool --offload {self.vm_resource.network_interfaces[self.n3_net_name].fixed.interface_name} rx off tx off")
        # ansible_builder.add_shell_task(f"ip r add 10.250.0.0/16 via 10.200.110.145 dev {self.vm_resource.network_interfaces['gnb-net'].fixed.interface_name}")



        ansible_builder.add_template_task(rel_path("config/n3_router.sh.jinja2"), "/opt/router.sh")
        ansible_builder.add_template_task(rel_path("config/router.service.jinja2"), "/etc/systemd/system/router.service")
        ansible_builder.set_var("side", "N3")
        ansible_builder.set_var("n3_if", self.vm_resource.network_interfaces[self.n3_net_name].fixed.interface_name)
        ansible_builder.set_var("ue_ip_pool_cidr", self.ue_ip_pool_cidr)
        ansible_builder.set_var("gnb_ip", self.gnb_ip)
        ansible_builder.set_var("gnb_if", self.vm_resource.network_interfaces[self.gnb_net_name].fixed.interface_name)

        ansible_builder.add_shell_task("systemctl daemon-reload")

        ansible_builder.add_service_task("router", ServiceState.STARTED, True)

        return ansible_builder.build()


class N6RouterConfigurator(VmResourceAnsibleConfiguration):
    upf_n6_ip: str = Field()
    n6_net_name: str = Field()
    mgt_net_name: str = Field()
    ue_ip_pool_cidr: str = Field()

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder(f"Playbook N6RouterConfigurator")

        # ansible_builder.add_shell_task("echo 1 > /proc/sys/net/ipv4/ip_forward")
        #
        # ansible_builder.add_shell_task(f"ip r add 10.250.0.0/16 via {self.upf_n6_ip} dev {n6_if}")
        # ansible_builder.add_shell_task(f"ethtool --offload {n6_if} rx off tx off")
        #
        # ansible_builder.add_shell_task(f"iptables -t nat -A POSTROUTING -o {internet_if} -j MASQUERADE")
        # ansible_builder.add_shell_task(f"iptables -A FORWARD -i {n6_if} -o {internet_if} -j ACCEPT")
        # ansible_builder.add_shell_task(f"iptables -A FORWARD -i {internet_if} -o {n6_if} -m state --state RELATED,ESTABLISHED -j ACCEPT")

        ansible_builder.add_template_task(rel_path("config/n6_router.sh.jinja2"), "/opt/router.sh")
        ansible_builder.add_template_task(rel_path("config/router.service.jinja2"), "/etc/systemd/system/router.service")
        ansible_builder.set_var("side", "N6")
        ansible_builder.set_var("n6_if", self.vm_resource.network_interfaces[self.n6_net_name].fixed.interface_name)
        ansible_builder.set_var("internet_if", self.vm_resource.network_interfaces[self.mgt_net_name].fixed.interface_name)
        ansible_builder.set_var("ue_ip_pool_cidr", self.ue_ip_pool_cidr)
        ansible_builder.set_var("upf_n6_ip", self.upf_n6_ip)

        ansible_builder.add_shell_task("systemctl daemon-reload")

        ansible_builder.add_service_task("router", ServiceState.STARTED, True)

        return ansible_builder.build()

class SDCoreUPFConfigurator(VmResourceAnsibleConfiguration):
    configuration: Optional[SDCoreUPFConfiguration] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder(f"Playbook SDCoreUPFConfigurator")

        upf_config_path = f"/opt/upf/upf.jsonc"
        run_upf_config_path = f"/opt/upf/run_upf.env"

        ansible_builder.add_template_task(rel_path("config/upf.jsonc.jinja2"), upf_config_path)
        ansible_builder.add_template_task(rel_path("config/run_upf.env.jinja2"), run_upf_config_path)

        ansible_builder.set_vars_from_fields(self.configuration)

        if self.configuration.start:
            ansible_builder.add_service_task("sdcore-upf", ServiceState.RESTARTED, True)

        return ansible_builder.build()


UPF_IMAGE_NAME = "sd-core-upf-v0.4.0-3"
UPF_IMAGE_URL = "https://images.tnt-lab.unige.it/sd-core-upf/sd-core-upf-v0.4.0-3.qcow2"


@declare_blue_type(SDCORE_UPF_BLUE_TYPE)
class SdCoreUPFBlueprintNG(BlueprintNG[SdCoreUPFBlueprintNGState, SdCoreUPFCreateModel]):
    sdcore_upf_image = VmResourceImage(name=UPF_IMAGE_NAME, url=UPF_IMAGE_URL)
    router_image = VmResourceImage(name="ubuntu2204")
    sdcore_upf_flavor = VmResourceFlavor(vcpu_count='4', memory_mb='8192', storage_gb='10')
    router_flavor = VmResourceFlavor(vcpu_count='1', memory_mb='1024', storage_gb='5')

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = SdCoreUPFBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: SdCoreUPFCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of SdCoreBlueprintNG blueprint")

        self.state.upf_vm = VmResource(
            area=create_model.area_id,
            name=f"{self.id}_{create_model.area_id}_SDCORE_UPF_{create_model.dnn}",
            image=self.sdcore_upf_image,
            flavor=self.sdcore_upf_flavor,
            username="ubuntu",
            password="ubuntu",
            management_network=create_model.networks.mgt,
            additional_networks=[create_model.networks.n4, create_model.networks.n3, create_model.networks.n6],
            require_port_security_disabled=True
        )
        self.register_resource(self.state.upf_vm)
        self.provider.create_vm(self.state.upf_vm)





        # self.state.n3_router_vm = VmResource(
        #     area=create_model.area_id,
        #     name=f"{self.id}_{create_model.area_id}_SDCORE_UPF_ROUTER_N3",
        #     image=self.router_image,
        #     flavor=self.router_flavor,
        #     username="ubuntu",
        #     password="ubuntu",
        #     management_network=create_model.networks.mgt,
        #     additional_networks=[create_model.networks.n3, create_model.networks.gnb]
        # )
        # self.register_resource(self.state.n3_router_vm)
        # self.provider.create_vm(self.state.n3_router_vm)



        self.state.n6_router_vm = VmResource(
            area=create_model.area_id,
            name=f"{self.id}_{create_model.area_id}_SDCORE_UPF_ROUTER_N6",
            image=self.router_image,
            flavor=self.router_flavor,
            username="ubuntu",
            password="ubuntu",
            management_network=create_model.networks.mgt,
            additional_networks=[create_model.networks.n6],
            require_port_security_disabled=True
        )
        self.register_resource(self.state.n6_router_vm)
        self.provider.create_vm(self.state.n6_router_vm)



        # self.state.n3_router_vm_configurator = N3RouterConfigurator(
        #     vm_resource=self.state.n3_router_vm,
        #     n3_net_name=create_model.networks.n3,
        #     gnb_net_name=create_model.networks.gnb,
        #     gnb_ip=gnb_n3_ip,
        #     ue_ip_pool_cidr=ue_ip_pool_cidr
        # )
        # self.register_resource(self.state.n3_router_vm_configurator)
        # self.provider.configure_vm(self.state.n3_router_vm_configurator)


        self.state.n6_router_vm_configurator = N6RouterConfigurator(
            vm_resource=self.state.n6_router_vm,
            upf_n6_ip=self.state.upf_vm.network_interfaces[create_model.networks.n6].fixed.ip,
            n6_net_name=create_model.networks.n6,
            mgt_net_name=create_model.networks.mgt,
            ue_ip_pool_cidr=create_model.ue_ip_pool_cidr
        )
        self.register_resource(self.state.n6_router_vm_configurator)
        self.provider.configure_vm(self.state.n6_router_vm_configurator)

        self.state.upf_vm_configurator = SDCoreUPFConfigurator(vm_resource=self.state.upf_vm, configuration=SDCoreUPFConfiguration(
            upf_mode="dpdk",
            n3_nic_name=self.state.upf_vm.network_interfaces[create_model.networks.n3].fixed.interface_name,
            n6_nic_name=self.state.upf_vm.network_interfaces[create_model.networks.n6].fixed.interface_name,
            n3_net_cidr=self.state.upf_vm.network_interfaces[create_model.networks.n3].fixed.get_ip_prefix(),
            n6_net_cidr=self.state.upf_vm.network_interfaces[create_model.networks.n6].fixed.get_ip_prefix(),
            n3_nic_mac=self.state.upf_vm.network_interfaces[create_model.networks.n3].fixed.mac,
            n6_nic_mac=self.state.upf_vm.network_interfaces[create_model.networks.n6].fixed.mac,
            # n3_nh_ip=self.state.n3_router_vm.network_interfaces[create_model.networks.n3].fixed.ip,
            # n6_nh_ip=self.state.n6_router_vm.network_interfaces[create_model.networks.n6].fixed.ip,
            # n3_nh_mac=self.state.n3_router_vm.network_interfaces[create_model.networks.n3].fixed.mac,
            # n6_nh_mac=self.state.n6_router_vm.network_interfaces[create_model.networks.n6].fixed.mac,
            # n3_route=self.state.n3_router_vm.network_interfaces[create_model.networks.gnb].fixed.cidr,
            n3_nh_ip=create_model.gnb_n3_ip,
            n6_nh_ip=self.state.n6_router_vm.network_interfaces[create_model.networks.n6].fixed.ip,
            n3_nh_mac=create_model.gnb_n3_mac,
            n6_nh_mac=self.state.n6_router_vm.network_interfaces[create_model.networks.n6].fixed.mac,
            n3_route=self.state.upf_vm.network_interfaces[create_model.networks.n3].fixed.cidr,
            n6_route="0.0.0.0/0",
            start=create_model.start,
            dnn=create_model.dnn,
            ue_ip_pool_cidr=create_model.ue_ip_pool_cidr
        ))
        self.register_resource(self.state.upf_vm_configurator)
        self.provider.configure_vm(self.state.upf_vm_configurator)

    def get_n4_info(self) -> str:
        return self.state.upf_vm.network_interfaces[self.create_config.networks.n4].fixed.ip

    def set_gnb_info(self, gnb_info: GNBN3Info):
        configuration_before = copy.copy(self.state.upf_vm_configurator.configuration)
        self.state.upf_vm_configurator.configuration.n3_nh_mac = gnb_info.mac
        self.state.upf_vm_configurator.configuration.n3_nh_ip = gnb_info.ip
        self.state.upf_vm_configurator.configuration.start = True
        if self.state.upf_vm_configurator.configuration != configuration_before:
            self.provider.configure_vm(self.state.upf_vm_configurator)
        else:
            self.logger.info("The UPF configuration is unchanged, skipping configuration")

    @classmethod
    def rest_create(cls, msg: SdCoreUPFCreateModel, request: Request):
        return cls.api_day0_function(msg, request)
