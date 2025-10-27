

from typing import Optional, List

from pydantic import Field, field_validator

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG, BlueprintNGState
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core_models.linux.ip import Route
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address, SerializableIPv4Network
from nfvcl_core_models.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_models.blueprint_ng.core5g.common import Router5GNetworkInfo, NetworkEndPoint, NetworkEndPointWithType
from nfvcl_core_models.http_models import HttpRequestType
from nfvcl_common.utils.blue_utils import rel_path


class Router5GCreateModelNetworks(NFVCLBaseModel):
    mgt: Optional[NetworkEndPoint] = Field(default=None)
    gnb: Optional[NetworkEndPointWithType] = Field(default=None)
    core: Optional[NetworkEndPointWithType] = Field(default=None)
    n3: Optional[NetworkEndPointWithType] = Field(default=None)
    n6: Optional[NetworkEndPointWithType] = Field(default=None)

    @field_validator("mgt", mode="before")
    def str_to_network_endpoint(cls, v: object) -> object:
        if isinstance(v, str):
            return NetworkEndPoint(net_name=v)
        return v

    @field_validator("gnb","core", "n3", "n6", mode="before")
    def str_to_network_endpoint_with_type(cls, v: object) -> object:
        if isinstance(v, str):
            return NetworkEndPointWithType(net_name=v)
        return v


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
    router_image = VmResourceImage(name="ubuntu-lab-v0.1.4-ubuntu2204", url="https://images.tnt-lab.unige.it/ubuntu-lab/ubuntu-lab-v0.1.4-ubuntu2204.qcow2")
    router_flavor = VmResourceFlavor(vcpu_count='1', memory_mb='1024', storage_gb='15')

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
            management_network=create_model.networks.mgt.net_name,
            additional_networks=[create_model.networks.gnb.net_name, create_model.networks.core.net_name, create_model.networks.n3.net_name, create_model.networks.n6.net_name],
            require_port_security_disabled=True
        )
        self.register_resource(self.state.router_vm)
        self.provider.create_vm(self.state.router_vm)

        self.state.router_vm_configurator = RouterConfigurator(
            vm_resource=self.state.router_vm,
            n6_net_name=create_model.networks.n6.net_name,
            mgt_net_name=create_model.networks.mgt.net_name,
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
            n3_ip=SerializableIPv4Address(self.state.router_vm.network_interfaces[self.create_config.networks.n3.net_name][0].fixed.ip),
            n6_ip=SerializableIPv4Address(self.state.router_vm.network_interfaces[self.create_config.networks.n6.net_name][0].fixed.ip),
            gnb_ip=SerializableIPv4Address(self.state.router_vm.network_interfaces[self.create_config.networks.gnb.net_name][0].fixed.ip),
            gnb_cidr=SerializableIPv4Network(self.state.router_vm.network_interfaces[self.create_config.networks.gnb.net_name][0].fixed.cidr)
        )
