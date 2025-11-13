from abc import abstractmethod
from typing import Generic, TypeVar, Dict, Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import Generic5GUPFBlueprintNGState, Generic5GUPFBlueprintNG, Router5GInfo
from nfvcl.blueprints_ng.modules.router_5g.router_5g import Router5GCreateModel, Router5GCreateModelNetworks, Router5GAddRouteModel
from nfvcl_core_models.linux.ip import Route
from nfvcl_models.blueprint_ng.core5g.common import Router5GNetworkInfo
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.network.network_models import MultusInterface
from nfvcl_core_models.resources import HelmChartResource


class K8sUPFMultusNetworkInfo(NFVCLBaseModel):
    n4: Optional[MultusInterface] = Field(default=None)
    n3: Optional[MultusInterface] = Field(default=None)
    n6: Optional[MultusInterface] = Field(default=None)

class Generic5GUPFK8SBlueprintNGState(Generic5GUPFBlueprintNGState):
    helm_chart_resources: Dict[str, HelmChartResource] = Field(default_factory=dict)
    multus_network_info: K8sUPFMultusNetworkInfo = Field(default_factory=K8sUPFMultusNetworkInfo)

StateTypeVar5GUPFK8S = TypeVar("StateTypeVar5GUPFK8S", bound=Generic5GUPFK8SBlueprintNGState)
CreateConfigTypeVar5GUPFK8S = TypeVar("CreateConfigTypeVar5GUPFK8S")

ROUTER_BLUEPRINT_TYPE = "router_5g_k8s"
ROUTER_GET_INFO_FUNCTION = "get_router_info"
ROUTER_ADD_ROUTES = "add_routes"

class Generic5GUPFK8SBlueprintNG(Generic5GUPFBlueprintNG[Generic5GUPFK8SBlueprintNGState, UPFBlueCreateModel], Generic[StateTypeVar5GUPFK8S, CreateConfigTypeVar5GUPFK8S]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFK8SBlueprintNGState] = StateTypeVar5GUPFK8S):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GUPFK8S:
        return super().state

    @abstractmethod
    def create_upf(self):
        pass

    @abstractmethod
    def update_upf(self):
        pass

    def deploy_router_blueprint(self) -> Router5GInfo:
        self.logger.info(f"Deploying router")

        router_5g_create_model = Router5GCreateModel(
            area_id=self.state.current_config.area_id,
            networks=Router5GCreateModelNetworks(
                gnb=self.state.current_config.networks.gnb,
                n3=self.state.current_config.networks.n3,
                n6=self.state.current_config.networks.n6
            )
        )

        router_id = self.provider.create_blueprint(ROUTER_BLUEPRINT_TYPE, router_5g_create_model)
        self.register_children(router_id)
        # After the router has been deployed gather the network information
        router_info: Router5GNetworkInfo = self.provider.call_blueprint_function(router_id, ROUTER_GET_INFO_FUNCTION)
        self.state.router = Router5GInfo(external=False, blue_id=router_id, network=router_info)
        self.logger.info(f"Deployed router")

        return Router5GInfo(external=False, blue_id=router_id, network=router_info)


    def add_route_to_router(self, cidr: str, nexthop: str):
        if self.state.router.external:
            # TODO in the future the external router may be configured by NFVCL calling metalcl/netcl
            self.logger.warning(f"The router for area {self.state.current_config.area_id} is external, manually add the following route:")
            self.logger.warning(f"ip r add {cidr} via {nexthop}")
        else:
            self.provider.call_blueprint_function(self.state.router.blue_id, ROUTER_ADD_ROUTES, Router5GAddRouteModel(additional_routes=[
                Route(network_cidr=cidr, next_hop=nexthop),
            ]))


    def pre_create_upf(self):
        self.update_router_deployment()

        self.state.current_config.n3_gateway_ip = self.state.router.network.n3_ip
        self.state.current_config.n6_gateway_ip = self.state.router.network.n6_ip
        self.state.current_config.gnb_cidr = self.state.router.network.gnb_cidr

    def post_create_upf(self):
        if self.router_needed:
            for upf in self.state.upf_list:
                upf.router_gnb_ip = self.state.router.network.gnb_ip

    def post_update_upf(self):
        if self.router_needed:
            for upf in self.state.upf_list:
                upf.router_gnb_ip = self.state.router.network.gnb_ip
