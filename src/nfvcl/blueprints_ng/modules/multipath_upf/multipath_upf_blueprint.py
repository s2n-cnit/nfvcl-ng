import copy
from typing import Optional, List, Dict

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import Generic5GUPFBlueprintNG, Generic5GUPFBlueprintNGState, Router5GInfo, DeployedUPFInfo
from nfvcl.blueprints_ng.modules.router.router import (
    RouterCreateModel, NftablesTable, NftablesChain, RouterNetworkInfo,
)
from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.blue_utils import rel_path
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address
from nfvcl_core_models.resources import VmResource, VmResourceFlavor, VmResourceImage, VmResourceAnsibleConfiguration
from nfvcl_models.blueprint_ng.core5g.common import Router5GNetworkInfo
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo

ROUTER_BLUEPRINT_TYPE = "router"
ROUTER_GET_INFO_FUNCTION = "get_router_info"
ROUTER_ADD_ROUTES = "add_routes"

FREE5GC_UPF_BLUEPRINT_TYPE = "free5gc_upf"
SDCORE_UPF_BLUEPRINT_TYPE = "sdcore_upf"
UPF_GET_INFO_FUNCTION = "get_upfs_info"

PFCPAGENT_IMAGE_NAME = "sd-core-upf-v2.2.1-dev-s2n-6"
PFCPAGENT_IMAGE_URL = "https://images.tnt-lab.unige.it/sd-core-upf/sd-core-upf-v2.2.1-dev-s2n-6-ubuntu2404.qcow2"


# ===================================== PFCPAgent Configurator Models ============================


class PFCPAgentDatapathInfo(NFVCLBaseModel):
    """Network info for a single UPF datapath (bess or free5gc)"""
    mgmt_ip: str = Field(description="IP reachable from the PFCP agent (used for gRPC and SSH)")
    n3_ip: str = Field(description="N3 (access) IP of the datapath")
    n6_ip: str = Field(description="N6 (core) IP of the datapath")


class PFCPAgentRouterInfo(NFVCLBaseModel):
    """Network info for the internet router managed by the PFCP agent"""
    mgmt_ip: str = Field(description="Management IP of the internet router (used for SSH)")
    n6_interface: str = Field(description="N6 interface name on the internet router")


class PFCPAgentConfiguration(NFVCLBaseModel):
    """Configuration for the PFCP agent VM"""
    bess_dp: PFCPAgentDatapathInfo = Field(description="SD-Core (BESS) datapath info")
    free5gc_dp: PFCPAgentDatapathInfo = Field(description="free5GC datapath info")
    router_internet: PFCPAgentRouterInfo = Field(description="Internet router info")
    n3_nic_name: str = Field(description="N3 interface name on the PFCP agent VM")
    n6_nic_name: str = Field(description="N6 interface name on the PFCP agent VM")
    dnn: str = Field(description="Data Network Name")
    n4_ip: str = Field(description="N4 IP of the PFCP agent VM")
    ue_ip_pool_cidr: str = Field(description="UE IP pool CIDR")
    gnb_cidr: str = Field(description="GNB network CIDR for static route destination")
    gtpu_router_mgmt_ip: str = Field(description="GTP-U router management interface IP for static route next hop")


class PFCPAgentConfigurator(VmResourceAnsibleConfiguration):
    """Ansible configurator that writes upf.jsonc to the PFCP agent VM"""
    configuration: Optional[PFCPAgentConfiguration] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook PFCPAgentConfigurator")

        # Persistent routes via netplan
        routes_by_interface: Dict[str, list] = {
            self.vm_resource.get_management_interface().fixed.interface_name: [
                {
                    "destination": self.configuration.gnb_cidr,
                    "next_hop": self.configuration.gtpu_router_mgmt_ip,
                }
            ]
        }

        ansible_builder.set_var("routes_by_interface", routes_by_interface)
        ansible_builder.add_template_task(rel_path("config/netplan_routes.yaml.jinja2"), "/etc/netplan/90-routes.yaml")
        ansible_builder.add_shell_task("netplan apply")

        upf_config_path = "/opt/pfcpagent/upf.jsonc"
        ansible_builder.add_template_task(rel_path("config/upf.jsonc.jinja2"), upf_config_path)
        ansible_builder.set_vars_from_fields(self.configuration)

        ansible_builder.add_service_task("pfcpagent", ServiceState.RESTARTED, True)

        return ansible_builder.build()


# ===================================== State ====================================================


class MultiPathUPFBlueprintNGState(Generic5GUPFBlueprintNGState):
    gtpu_router_id: Optional[str] = Field(default=None, description="Blueprint ID of the GTP-U router")
    internet_router_id: Optional[str] = Field(default=None, description="Blueprint ID of the internet router")
    pfcpagent_vm: Optional[VmResource] = Field(default=None, description="VM resource for the PFCP agent")
    pfcpagent_configurator: Optional[PFCPAgentConfigurator] = Field(default=None, description="Configurator for the PFCP agent VM")
    free5gc_upf_id: Optional[str] = Field(default=None, description="Blueprint ID of the free5gc UPF")
    sdcore_upf_id: Optional[str] = Field(default=None, description="Blueprint ID of the sdcore UPF")


@blueprint_type("multipath_upf")
class MultiPathUPFBlueprintNG(Generic5GUPFBlueprintNG[MultiPathUPFBlueprintNGState, UPFBlueCreateModel]):
    router_needed = False # We deploy the routers manually in this bp

    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFBlueprintNGState] = MultiPathUPFBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> MultiPathUPFBlueprintNGState:
        return super().state

    def deploy_router_blueprint(self) -> Router5GInfo:
        # Not used directly; routers are deployed in create_upf
        raise NotImplementedError("MultiPathUPFBlueprintNG deploys routers directly in create_upf")

    def add_route_to_router(self, cidr: str, nexthop: str):
        # Routes are handled by the pfcpagent in this blueprint
        pass

    def create_upf(self):
        self.logger.info("Starting creation of MultiPathUPFBlueprintNG blueprint")

        mgt_net_name = self.state.current_config.networks.mgt.net_name
        n3_net_name = self.state.current_config.networks.n3.net_name
        n4_net_name = self.state.current_config.networks.n4.net_name
        n6_net_name = self.state.current_config.networks.n6.net_name
        gnb_net_name = self.state.current_config.networks.gnb.net_name

        # ---- Deploy GTP-U Router (management, n3, n4, gnb) ----
        self.logger.info("Deploying GTP-U router")
        gtpu_router_create_model = RouterCreateModel(
            area_id=self.state.current_config.area_id,
            management_network=mgt_net_name,
            additional_networks=[n3_net_name, n4_net_name, gnb_net_name],
            enable_forwarding=True,
        )

        self.state.gtpu_router_id = self.provider.create_blueprint(ROUTER_BLUEPRINT_TYPE, gtpu_router_create_model)
        self.register_children(self.state.gtpu_router_id)
        gtpu_router_info: RouterNetworkInfo = self.provider.call_blueprint_function(
            self.state.gtpu_router_id, ROUTER_GET_INFO_FUNCTION
        )
        self.logger.info(f"Deployed GTP-U router: {self.state.gtpu_router_id}")

        # ---- Deploy Internet Router (management, n6) with NAT masquerade ----
        self.logger.info("Deploying internet router")
        internet_router_create_model = RouterCreateModel(
            area_id=self.state.current_config.area_id,
            management_network=mgt_net_name,
            additional_networks=[n6_net_name],
            enable_forwarding=True,
            nftables_tables=[
                NftablesTable(
                    family="inet",
                    name="filter",
                    chains=[
                        NftablesChain(
                            name="forward",
                            type="filter",
                            hook="forward",
                            priority=0,
                            policy="accept",
                        )
                    ]
                ),
                NftablesTable(
                    family="ip",
                    name="nat",
                    chains=[
                        NftablesChain(
                            name="postrouting",
                            type="nat",
                            hook="postrouting",
                            priority=100,
                            policy="accept",
                            rules=[f'oifname "{{net:{mgt_net_name}}}" masquerade'],
                        )
                    ]
                ),
            ],
        )

        self.state.internet_router_id = self.provider.create_blueprint(ROUTER_BLUEPRINT_TYPE, internet_router_create_model)
        self.register_children(self.state.internet_router_id)
        internet_router_info: RouterNetworkInfo = self.provider.call_blueprint_function(
            self.state.internet_router_id, ROUTER_GET_INFO_FUNCTION
        )
        self.logger.info(f"Deployed internet router: {self.state.internet_router_id}")

        # ---- Deploy PFCP agent VM ----
        self.state.pfcpagent_vm = VmResource(
            area=self.state.current_config.area_id,
            name=f"{self.id}_{self.state.current_config.area_id}_PFCPAGENT",
            image=VmResourceImage(name=PFCPAGENT_IMAGE_NAME, url=PFCPAGENT_IMAGE_URL),
            flavor=VmResourceFlavor(vcpu_count='4', memory_mb='8192', storage_gb='10'),
            username="ubuntu",
            password="ubuntu",
            management_network=self.state.current_config.networks.mgt.net_name,
            additional_networks=[self.state.current_config.networks.n4.net_name, self.state.current_config.networks.n3.net_name],
            require_port_security_disabled=True
        )
        self.register_resource(self.state.pfcpagent_vm)
        self.provider.create_vm(self.state.pfcpagent_vm)

        # ---- Build combined router info for parent state ----
        self.state.router = Router5GInfo(
            external=False,
            blue_id=self.state.gtpu_router_id,
            network=Router5GNetworkInfo(
                n3_ip=gtpu_router_info.interfaces[n3_net_name].ip,
                n6_ip=internet_router_info.interfaces[n6_net_name].ip,
                gnb_ip=gtpu_router_info.interfaces[gnb_net_name].ip,
                gnb_cidr=gtpu_router_info.interfaces[gnb_net_name].cidr,
            )
        )

        # Set gateway IPs on the current config for UPF deployment
        self.state.current_config.n3_gateway_ip = SerializableIPv4Address(self.state.pfcpagent_vm.network_interfaces[n3_net_name][0].fixed.ip) # Packets should return to pfcpagent instead of going directly back to gnb
        self.state.current_config.n6_gateway_ip = self.state.router.network.n6_ip
        self.state.current_config.gnb_cidr = self.state.router.network.gnb_cidr

        # Provide router info as external_router so child UPFs don't deploy their own routers
        self.state.current_config.external_router = Router5GNetworkInfo(
            n3_ip=SerializableIPv4Address(self.state.pfcpagent_vm.network_interfaces[n3_net_name][0].fixed.ip),
            n6_ip=self.state.router.network.n6_ip,
            gnb_ip=self.state.router.network.gnb_ip,
            gnb_cidr=self.state.router.network.gnb_cidr,
        )

        # ---- Deploy free5gc UPF ----
        self.logger.info("Deploying free5gc UPF")
        free5gc_upf_create_model = copy.deepcopy(self.state.current_config)
        free5gc_upf_create_model.only_datapath = True
        self.state.free5gc_upf_id = self.provider.create_blueprint(FREE5GC_UPF_BLUEPRINT_TYPE, free5gc_upf_create_model)
        self.register_children(self.state.free5gc_upf_id)
        free5gc_upf_info: List[DeployedUPFInfo] = self.provider.call_blueprint_function(
            self.state.free5gc_upf_id, UPF_GET_INFO_FUNCTION
        )
        # self.state.upf_list.extend(free5gc_upf_info)
        self.logger.info(f"Deployed free5gc UPF: {self.state.free5gc_upf_id}")

        # ---- Deploy sdcore UPF ----
        self.logger.info("Deploying sdcore UPF")
        sdcore_upf_create_model = copy.deepcopy(self.state.current_config)
        sdcore_upf_create_model.only_datapath = True
        self.state.sdcore_upf_id = self.provider.create_blueprint(SDCORE_UPF_BLUEPRINT_TYPE, sdcore_upf_create_model)
        self.register_children(self.state.sdcore_upf_id)
        sdcore_upf_info: List[DeployedUPFInfo] = self.provider.call_blueprint_function(
            self.state.sdcore_upf_id, UPF_GET_INFO_FUNCTION
        )
        # self.state.upf_list.extend(sdcore_upf_info)
        self.logger.info(f"Deployed sdcore UPF: {self.state.sdcore_upf_id}")

        # ---- configure pfcpagent ----
        self.logger.info("Configuring PFCP agent VM")

        n4_net_name = self.state.current_config.networks.n4.net_name
        n3_net_name = self.state.current_config.networks.n3.net_name
        n6_net_name = self.state.current_config.networks.n6.net_name
        mgt_net_name = self.state.current_config.networks.mgt.net_name

        # Gather datapath info from the deployed child UPFs
        # Use n4 IPs as the reachable address for gRPC/SSH (pfcpagent shares the n4 network)
        sdcore_upf_deployed = sdcore_upf_info[0]
        free5gc_upf_deployed = free5gc_upf_info[0]

        bess_dp = PFCPAgentDatapathInfo(
            mgmt_ip=str(sdcore_upf_deployed.network_info.n4_ip),
            n3_ip=str(sdcore_upf_deployed.network_info.n3_ip),
            n6_ip=str(sdcore_upf_deployed.network_info.n6_ip),
        )
        free5gc_dp = PFCPAgentDatapathInfo(
            mgmt_ip=str(free5gc_upf_deployed.network_info.n4_ip),
            n3_ip=str(free5gc_upf_deployed.network_info.n3_ip),
            n6_ip=str(free5gc_upf_deployed.network_info.n6_ip),
        )
        router_internet = PFCPAgentRouterInfo(
            mgmt_ip=str(internet_router_info.interfaces[mgt_net_name].ip),
            n6_interface=internet_router_info.interfaces[n6_net_name].interface_name,
        )

        # Resolve the first DNN and its UE IP pool from the slice config
        first_dnn = self.state.current_config.slices[0].dnn_list[0].dnn
        first_dnn_cidr = self.state.current_config.slices[0].dnn_list[0].cidr

        pfcpagent_n4_ip = self.state.pfcpagent_vm.network_interfaces[n4_net_name][0].fixed.ip
        pfcpagent_n3_nic = self.state.pfcpagent_vm.network_interfaces[n3_net_name][0].fixed.interface_name

        pfcpagent_config = PFCPAgentConfiguration(
            bess_dp=bess_dp,
            free5gc_dp=free5gc_dp,
            router_internet=router_internet,
            n3_nic_name=pfcpagent_n3_nic,
            n6_nic_name=pfcpagent_n3_nic, # There is no N6 interface used here, but it's necessary or the pfcpagent won't start
            dnn=first_dnn,
            n4_ip=pfcpagent_n4_ip,
            ue_ip_pool_cidr=first_dnn_cidr,
            gnb_cidr=str(gtpu_router_info.interfaces[gnb_net_name].cidr),
            gtpu_router_mgmt_ip=str(gtpu_router_info.interfaces[mgt_net_name].ip),
        )

        self.state.pfcpagent_configurator = PFCPAgentConfigurator(
            vm_resource=self.state.pfcpagent_vm,
            configuration=pfcpagent_config,
        )
        self.register_resource(self.state.pfcpagent_configurator)
        self.provider.configure_vm(self.state.pfcpagent_configurator)

        deployed_upf_info = DeployedUPFInfo(
            area=self.state.current_config.area_id,
            served_slices=self.state.current_config.slices,
            vm_resource_id=self.state.pfcpagent_vm.id,
            vm_configurator_id=self.state.pfcpagent_configurator.id,
            network_info=UPFNetworkInfo(
                n4_cidr=SerializableIPv4Network(self.state.pfcpagent_vm.network_interfaces[self.state.current_config.networks.n4.net_name][0].fixed.cidr),
                n3_cidr=SerializableIPv4Network(self.state.pfcpagent_vm.network_interfaces[self.state.current_config.networks.n3.net_name][0].fixed.cidr),
                n6_cidr=SerializableIPv4Network(sdcore_upf_deployed.network_info.n6_cidr),
                n4_ip=SerializableIPv4Address(self.state.pfcpagent_vm.network_interfaces[self.state.current_config.networks.n4.net_name][0].fixed.ip),
                n3_ip=SerializableIPv4Address(self.state.pfcpagent_vm.network_interfaces[self.state.current_config.networks.n3.net_name][0].fixed.ip),
                n6_ip=SerializableIPv4Address("0.0.0.0") # Dummy ip, this field is used to set routes, but here it's handled by the pfcpagent
            ),
            router_gnb_ip=SerializableIPv4Address(gtpu_router_info.interfaces[gnb_net_name].ip),
        )
        self.state.upf_list.clear()
        self.state.upf_list.append(deployed_upf_info)

        self.logger.info("PFCP agent VM configured")

    def update_upf(self):
        self.logger.debug("MultiPathUPFBlueprintNG update")
