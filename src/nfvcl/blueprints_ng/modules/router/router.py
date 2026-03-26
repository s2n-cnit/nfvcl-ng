from typing import Optional, List, Dict

from pydantic import Field

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG, BlueprintNGState
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address, SerializableIPv4Network
from nfvcl_core_models.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_common.utils.blue_utils import rel_path


# ===================================== Models =============================================


class NftablesChain(NFVCLBaseModel):
    """Represents an nftables chain within a table"""
    name: str = Field(description="Chain name")
    type: str = Field(description="Chain type: filter, nat, route")
    hook: str = Field(description="Nftables hook: input, output, forward, prerouting, postrouting")
    priority: int = Field(default=0, description="Chain priority")
    policy: str = Field(default="accept", description="Default chain policy: accept or drop")
    rules: List[str] = Field(default_factory=list, description="List of nftables rule expressions")


class NftablesTable(NFVCLBaseModel):
    """Represents an nftables table"""
    family: str = Field(description="Address family: inet, ip, ip6, bridge, arp, netdev")
    name: str = Field(description="Table name")
    chains: List[NftablesChain] = Field(default_factory=list, description="List of chains in the table")


class RouterStaticRoute(NFVCLBaseModel):
    """A static route to be configured on the router via netplan"""
    network_name: str = Field(description="Network name the route is associated with (must be one of the connected networks)")
    destination: str = Field(description="Destination network CIDR")
    next_hop: str = Field(description="Next hop IP address")


class RouterCreateModel(BlueprintNGCreateModel):
    """Create model for the generic router blueprint"""
    area_id: int = Field(description="Area ID for the router VM")
    management_network: str = Field(description="Name of the management network")
    additional_networks: List[str] = Field(default_factory=list, description="Additional network names to connect the router to")
    static_routes: List[RouterStaticRoute] = Field(default_factory=list, description="List of static routes to configure")
    nftables_tables: List[NftablesTable] = Field(default_factory=list, description="List of nftables tables with chains and rules")
    enable_forwarding: bool = Field(default=True, description="Enable IP forwarding on the router")


class RouterAddRouteModel(NFVCLBaseModel):
    """Day2 model to add static routes to the router"""
    static_routes: List[RouterStaticRoute] = Field(default_factory=list, description="Static routes to add")


class RouterUpdateNftablesModel(NFVCLBaseModel):
    """Day2 model to replace the nftables configuration on the router"""
    nftables_tables: List[NftablesTable] = Field(default_factory=list, description="New nftables tables configuration (replaces the existing one)")


class RouterNetworkInterfaceInfo(NFVCLBaseModel):
    """Information about a single network interface on the router"""
    ip: Optional[SerializableIPv4Address] = Field(default=None, description="IP address of the interface")
    cidr: Optional[SerializableIPv4Network] = Field(default=None, description="CIDR of the network")
    interface_name: Optional[str] = Field(default=None, description="Name of the network interface")


class RouterNetworkInfo(NFVCLBaseModel):
    """Generic network information for the router"""
    interfaces: Dict[str, RouterNetworkInterfaceInfo] = Field(default_factory=dict, description="Map of network name to interface info")


# ===================================== Configurator =======================================


class RouterConfigurator(VmResourceAnsibleConfiguration):
    """Ansible configurator for the generic router"""
    management_network: str = Field(description="Name of the management network")
    additional_networks: List[str] = Field(default_factory=list, description="Additional network names")
    static_routes: List[RouterStaticRoute] = Field(default_factory=list, description="Static routes")
    nftables_tables: List[NftablesTable] = Field(default_factory=list, description="Nftables configuration")
    enable_forwarding: bool = Field(default=True, description="Enable IP forwarding")

    def _build_interface_mapping(self) -> Dict[str, str]:
        """Build a mapping from network name to interface name"""
        interfaces: Dict[str, str] = {}
        for net_name in [self.management_network] + self.additional_networks:
            if net_name in self.vm_resource.network_interfaces:
                interfaces[net_name] = self.vm_resource.network_interfaces[net_name][0].fixed.interface_name
        return interfaces

    @staticmethod
    def _resolve_net_placeholders(rule: str, interfaces: Dict[str, str]) -> str:
        """Resolve {net:name} placeholders in a rule string to actual interface names"""
        for net_name, if_name in interfaces.items():
            rule = rule.replace(f"{{net:{net_name}}}", if_name)
        return rule

    def _resolve_nftables_tables(self, interfaces: Dict[str, str]) -> List[dict]:
        """Resolve {net:name} placeholders in all nftables rules and return serialized tables"""
        resolved_tables = []
        for table in self.nftables_tables:
            table_dict = table.model_dump()
            for chain in table_dict["chains"]:
                chain["rules"] = [
                    self._resolve_net_placeholders(rule, interfaces)
                    for rule in chain["rules"]
                ]
            resolved_tables.append(table_dict)
        return resolved_tables

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder(f"Playbook RouterConfigurator")

        interfaces = self._build_interface_mapping()
        ansible_builder.set_var("interfaces", interfaces)

        # Persistent IP forwarding via sysctl
        if self.enable_forwarding:
            ansible_builder.add_copy_task(rel_path("config/sysctl_ipforward.conf"), "/etc/sysctl.d/99-ip-forward.conf")
        else:
            ansible_builder.add_copy_task(rel_path("config/sysctl_ipforward_disabled.conf"), "/etc/sysctl.d/99-ip-forward.conf")
        ansible_builder.add_shell_task("sysctl --system")

        # Persistent firewall rules via nftables (resolve {net:name} placeholders)
        resolved_tables = self._resolve_nftables_tables(interfaces)
        if resolved_tables:
            ansible_builder.set_var("nftables_tables", resolved_tables)
        ansible_builder.add_template_task(rel_path("config/nftables_rules.conf.jinja2"), "/etc/nftables.conf")
        ansible_builder.add_service_task("nftables", ServiceState.RESTARTED, True)

        # Persistent routes via netplan
        routes_by_interface: Dict[str, list] = {}
        for route in self.static_routes:
            if_name = interfaces.get(route.network_name)
            if if_name:
                if if_name not in routes_by_interface:
                    routes_by_interface[if_name] = []
                routes_by_interface[if_name].append({
                    "destination": route.destination,
                    "next_hop": route.next_hop,
                })
        if routes_by_interface:
            ansible_builder.set_var("routes_by_interface", routes_by_interface)
        ansible_builder.add_template_task(rel_path("config/netplan_routes.yaml.jinja2"), "/etc/netplan/90-router-routes.yaml")
        ansible_builder.add_shell_task("netplan apply")

        # Ethtool offload via systemd service for all additional interfaces
        offload_interfaces = [interfaces[net] for net in self.additional_networks if net in interfaces]
        if offload_interfaces:
            ansible_builder.set_var("offload_interfaces", offload_interfaces)
        ansible_builder.add_template_task(rel_path("config/router.sh.jinja2"), "/opt/router.sh")
        ansible_builder.add_template_task(rel_path("config/router.service.jinja2"), "/etc/systemd/system/router.service")
        ansible_builder.add_shell_task("systemctl daemon-reload")
        ansible_builder.add_service_task("router", ServiceState.RESTARTED, True)

        return ansible_builder.build()


# ===================================== State ==============================================


class RouterBlueprintNGState(BlueprintNGState):
    router_vm: Optional[VmResource] = Field(default=None)
    router_vm_configurator: Optional[RouterConfigurator] = Field(default=None)


# ===================================== Blueprint ==========================================


@blueprint_type("router")
class RouterBlueprintNG(BlueprintNG[RouterBlueprintNGState, RouterCreateModel]):
    router_image = VmResourceImage(name="ubuntu-lab-v0.1.5-ubuntu2404", url="https://images.tnt-lab.unige.it/ubuntu-lab/ubuntu-lab-v0.1.5-ubuntu2404.qcow2")
    router_flavor = VmResourceFlavor(vcpu_count='1', memory_mb='1024', storage_gb='15')

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = RouterBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: RouterCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of RouterBlueprintNG blueprint")

        self.state.router_vm = VmResource(
            area=create_model.area_id,
            name=f"{self.id}_{create_model.area_id}_ROUTER",
            image=self.router_image,
            flavor=self.router_flavor,
            username="ubuntu",
            password="ubuntu",
            management_network=create_model.management_network,
            additional_networks=create_model.additional_networks,
            require_port_security_disabled=True
        )
        self.register_resource(self.state.router_vm)
        self.provider.create_vm(self.state.router_vm)

        self.state.router_vm_configurator = RouterConfigurator(
            vm_resource=self.state.router_vm,
            management_network=create_model.management_network,
            additional_networks=create_model.additional_networks,
            static_routes=create_model.static_routes,
            nftables_tables=create_model.nftables_tables,
            enable_forwarding=create_model.enable_forwarding,
        )
        self.register_resource(self.state.router_vm_configurator)
        self.provider.configure_vm(self.state.router_vm_configurator)

    @day2_function("/add_routes", [HttpRequestType.PUT])
    def add_routes(self, model: RouterAddRouteModel):
        """Add static routes to the router and reconfigure"""
        self.state.router_vm_configurator.static_routes.extend(model.static_routes)
        self.provider.configure_vm(self.state.router_vm_configurator)

    @day2_function("/update_nftables", [HttpRequestType.PUT])
    def update_nftables(self, model: RouterUpdateNftablesModel):
        """Replace the nftables configuration and reconfigure"""
        self.state.router_vm_configurator.nftables_tables = model.nftables_tables
        self.provider.configure_vm(self.state.router_vm_configurator)

    def get_router_info(self) -> RouterNetworkInfo:
        """Get network information for all connected interfaces"""
        interfaces: Dict[str, RouterNetworkInterfaceInfo] = {}
        all_networks = [self.create_config.management_network] + self.create_config.additional_networks
        for net_name in all_networks:
            if net_name in self.state.router_vm.network_interfaces:
                net_if = self.state.router_vm.network_interfaces[net_name][0].fixed
                interfaces[net_name] = RouterNetworkInterfaceInfo(
                    ip=SerializableIPv4Address(net_if.ip),
                    cidr=SerializableIPv4Network(net_if.cidr),
                    interface_name=net_if.interface_name,
                )
        return RouterNetworkInfo(interfaces=interfaces)
