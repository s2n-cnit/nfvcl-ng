from abc import abstractmethod
from typing import Generic, TypeVar, Dict, Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import Generic5GUPFBlueprintNGState, Generic5GUPFBlueprintNG
from nfvcl.blueprints_ng.modules.router_5g.router_5g import Router5GCreateModel, Router5GCreateModelNetworks, Router5GAddRouteModel
from nfvcl.models.blueprint_ng.core5g.common import Router5GNetworkInfo
from nfvcl.models.blueprint_ng.g5.upf import UPFBlueCreateModel
from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.linux.ip import Route
from nfvcl_core.models.resources import VmResource


class Router5GInfo(NFVCLBaseModel):
    blue_id: Optional[str] = Field(default=None)
    external: bool = Field()
    network: Router5GNetworkInfo = Field()

class Generic5GUPFVMBlueprintNGState(Generic5GUPFBlueprintNGState):
    vm_resources: Dict[str, VmResource] = Field(default_factory=dict)
    router: Optional[Router5GInfo] = Field(default=None)


StateTypeVar5GUPFVM = TypeVar("StateTypeVar5GUPFVM", bound=Generic5GUPFVMBlueprintNGState)
CreateConfigTypeVar5GUPFVM = TypeVar("CreateConfigTypeVar5GUPFVM")

ROUTER_BLUEPRINT_TYPE = "router_5g"
ROUTER_GET_INFO_FUNCTION = "get_router_info"
ROUTER_ADD_ROUTES = "add_routes"


class Generic5GUPFVMBlueprintNG(Generic5GUPFBlueprintNG[Generic5GUPFVMBlueprintNGState, UPFBlueCreateModel], Generic[StateTypeVar5GUPFVM, CreateConfigTypeVar5GUPFVM]):
    router_needed: bool = True

    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFVMBlueprintNGState] = StateTypeVar5GUPFVM):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GUPFVM:
        return super().state

    def update_router_deployment(self):
        if self.router_needed:
            router_info: Router5GInfo
            if True: #not area.networks.external_router: TODO fix this
                router_info = self.deploy_router_blueprint()
            else:
                pass
                # router_info = Router5GInfo(external=True, network=area.networks.external_router)
            self.state.router = router_info

    def deploy_router_blueprint(self) -> Router5GInfo:
        """
        Deploy the router blueprint

        Returns: Router5GInfo for the deployed router
        """
        self.logger.info(f"Deploying router")

        router_5g_create_model = Router5GCreateModel(
            area_id=self.state.current_config.area_id,
            networks=Router5GCreateModelNetworks(
                mgt=self.state.current_config.networks.mgt.net_name,
                gnb=self.state.current_config.networks.gnb.net_name,
                core=self.state.current_config.networks.n4.net_name,
                n3=self.state.current_config.networks.n3.net_name,
                n6=self.state.current_config.networks.n6.net_name
            )
        )

        router_id = self.provider.create_blueprint(ROUTER_BLUEPRINT_TYPE, router_5g_create_model)
        self.register_children(router_id)
        # After the router has been deployed gather the network information
        router_info: Router5GNetworkInfo = self.provider.call_blueprint_function(router_id, ROUTER_GET_INFO_FUNCTION)
        self.logger.info(f"Deployed router")

        self.state.current_config.n3_gateway_ip = router_info.n3_ip
        self.state.current_config.n6_gateway_ip = router_info.n6_ip
        self.state.current_config.gnb_cidr = router_info.gnb_cidr

        return Router5GInfo(external=False, blue_id=router_id, network=router_info)

    def add_route_to_router(self, cidr: str, nexthop: str):
        """
        Add a route to the router in the specified area
        Args:
            cidr: The network cidr of the network to route
            nexthop: The nexthop of the route
        """
        router_info = self.state.router
        if router_info.external:
            # TODO in the future the external router may be configured by NFVCL calling metalcl/netcl
            self.logger.warning(f"The router for area {self.state.current_config.area_id} is external, manually add the following route:")
            self.logger.warning(f"ip r add {cidr} via {nexthop}")
        else:
            self.logger.info(f"Adding route '{cidr}' via '{nexthop}' to router {router_info.blue_id}")
            self.provider.call_blueprint_function(router_info.blue_id, ROUTER_ADD_ROUTES, Router5GAddRouteModel(additional_routes=[
                Route(network_cidr=cidr, next_hop=nexthop)
            ]))

    def update_router_routes(self):
        # The router need to route the traffic for the DNN ip pool through the UPF N6 interface
        if self.router_needed:
            for deployed_upf in self.state.upf_list:
                for slice in deployed_upf.served_slices:
                    for dnn in slice.dnn_list:
                        self.add_route_to_router(dnn.cidr, deployed_upf.network_info.n6_ip.exploded)

    def pre_create_upf(self):
        self.update_router_deployment()
        self.update_router_routes()

    @abstractmethod
    def create_upf(self):
        pass

    def post_create_upf(self):
        if self.router_needed:
            for upf in self.state.upf_list:
                upf.router_gnb_ip = self.state.router.network.gnb_ip

    def pre_update_upf(self):
        self.state.current_config.n3_gateway_ip = self.state.router.network.n3_ip
        self.state.current_config.n6_gateway_ip = self.state.router.network.n6_ip
        self.state.current_config.gnb_cidr = self.state.router.network.gnb_cidr
        self.update_router_routes()

    @abstractmethod
    def update_upf(self):
        pass

    def post_update_upf(self):
        if self.router_needed:
            for upf in self.state.upf_list:
                upf.router_gnb_ip = self.state.router.network.gnb_ip
