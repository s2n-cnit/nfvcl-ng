from __future__ import annotations

from typing import Optional, List

from pydantic import Field

from nfvcl.blueprints_ng.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState, BlueprintNGCreateModel
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type, day2_function
from nfvcl.blueprints_ng.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration
from nfvcl.blueprints_ng.utils import rel_path
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint_ng.core5g.common import Router5GNetworkInfo
from nfvcl.models.http_models import HttpRequestType
from nfvcl.models.linux.ip import Route
from nfvcl.models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address


class Router5GCreateModelNetworks(NFVCLBaseModel):
    mgt: str = Field()
    gnb: str = Field()
    core: str = Field()
    n3: str = Field()
    n6: str = Field()


class Router5GCreateModel(BlueprintNGCreateModel):
    area_id: int = Field()
    networks: Router5GCreateModelNetworks = Field()
    additional_routes: Optional[List[Route]] = Field(default_factory=list)


class Router5GBlueprintNGState(BlueprintNGState):
    router_vm: Optional[VmResource] = Field(default=None)
    router_vm_configurator: Optional[RouterConfigurator] = Field(default=None)


class Router5GAddRouteModel(NFVCLBaseModel):
    additional_routes: Optional[List[Route]] = Field(default_factory=list)


class RouterConfigurator(VmResourceAnsibleConfiguration):
    n6_net_name: str = Field()
    mgt_net_name: str = Field()
    additional_routes: Optional[List[Route]] = Field(default_factory=list)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder(f"Playbook RouterConfigurator")

        ansible_builder.add_template_task(rel_path("config/router.sh.jinja2"), "/opt/router.sh")
        ansible_builder.add_template_task(rel_path("config/router.service.jinja2"), "/etc/systemd/system/router.service")
        ansible_builder.set_var("n6_if", self.vm_resource.network_interfaces[self.n6_net_name][0].fixed.interface_name)
        ansible_builder.set_var("internet_if", self.vm_resource.network_interfaces[self.mgt_net_name][0].fixed.interface_name)

        if self.additional_routes and len(self.additional_routes) > 0:
            additional_routes_str: List[str] = []
            for route in self.additional_routes:
                additional_routes_str.append(route.as_linux_replace_command())
            ansible_builder.set_var("additional_routes", additional_routes_str)

        ansible_builder.add_shell_task("systemctl daemon-reload")

        ansible_builder.add_service_task("router", ServiceState.RESTARTED, True)

        return ansible_builder.build()


@blueprint_type("router_5g")
class Router5GBlueprintNG(BlueprintNG[Router5GBlueprintNGState, Router5GCreateModel]):
    router_image = VmResourceImage(name="ubuntu2204")
    router_flavor = VmResourceFlavor(vcpu_count='1', memory_mb='1024', storage_gb='5')

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = Router5GBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: Router5GCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of Router5GBlueprintNG blueprint")

        self.state.router_vm = VmResource(
            area=create_model.area_id,
            name=f"{self.id}_{create_model.area_id}_5G_ROUTER",
            image=self.router_image,
            flavor=self.router_flavor,
            username="ubuntu",
            password="ubuntu",
            management_network=create_model.networks.mgt,
            additional_networks=[create_model.networks.gnb, create_model.networks.core, create_model.networks.n3, create_model.networks.n6],
            require_port_security_disabled=True
        )
        self.register_resource(self.state.router_vm)
        self.provider.create_vm(self.state.router_vm)

        self.state.router_vm_configurator = RouterConfigurator(
            vm_resource=self.state.router_vm,
            n6_net_name=create_model.networks.n6,
            mgt_net_name=create_model.networks.mgt,
            additional_routes=create_model.additional_routes
        )
        self.register_resource(self.state.router_vm_configurator)
        self.provider.configure_vm(self.state.router_vm_configurator)

    @day2_function("/add_routes", [HttpRequestType.PUT])
    def add_routes(self, model: Router5GAddRouteModel):
        self.state.router_vm_configurator.additional_routes.extend(model.additional_routes)
        self.provider.configure_vm(self.state.router_vm_configurator)

    def get_router_info(self) -> Router5GNetworkInfo:
        return Router5GNetworkInfo(
            n3_ip=SerializableIPv4Address(self.state.router_vm.network_interfaces[self.create_config.networks.n3][0].fixed.ip),
            n6_ip=SerializableIPv4Address(self.state.router_vm.network_interfaces[self.create_config.networks.n6][0].fixed.ip),
            gnb_ip=SerializableIPv4Address(self.state.router_vm.network_interfaces[self.create_config.networks.gnb][0].fixed.ip),
            gnb_cidr=SerializableIPv4Network(self.state.router_vm.network_interfaces[self.create_config.networks.gnb][0].fixed.cidr)
        )
