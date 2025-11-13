import copy
from abc import abstractmethod
from typing import Generic, TypeVar, Optional, final, List

from nfvcl_core_models.network.ipam_models import SerializableIPv4Address
from pydantic import Field

from nfvcl_models.blueprint_ng.core5g.common import Router5GNetworkInfo
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo, Slice5GWithDNNs
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG, BlueprintNGState
from nfvcl_core.blueprints.blueprint_type_manager import day2_function
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.api_utils import HttpRequestType


class DeployedUPFInfo(NFVCLBaseModel):
    area: int = Field()
    served_slices: List[Slice5GWithDNNs] = Field(default_factory=list)
    network_info: Optional[UPFNetworkInfo] = Field(default=None)
    vm_resource_id: Optional[str] = Field(default=None)
    vm_configurator_id: Optional[str] = Field(default=None)
    helm_chart_resource_id: Optional[str] = Field(default=None)
    router_gnb_ip: Optional[SerializableIPv4Address] = Field(default=None)

    def served_dnns(self) -> List[str]:
        served_dnns_list: List[str] = []
        for served_slice in self.served_slices:
            for served_dnn in served_slice.dnn_list:
                served_dnns_list.append(served_dnn.dnn)
        return served_dnns_list

class Router5GInfo(NFVCLBaseModel):
    blue_id: Optional[str] = Field(default=None)
    external: bool = Field()
    network: Router5GNetworkInfo = Field()

class Generic5GUPFBlueprintNGState(BlueprintNGState):
    current_config: Optional[UPFBlueCreateModel] = Field(default=None)
    upf_list: List[DeployedUPFInfo] = Field(default_factory=list)
    router: Optional[Router5GInfo] = Field(default=None)


StateTypeVar5GUPF = TypeVar("StateTypeVar5GUPF", bound=Generic5GUPFBlueprintNGState)
CreateConfigTypeVar5GUPF = TypeVar("CreateConfigTypeVar5GUPF")


class Generic5GUPFBlueprintNG(BlueprintNG[Generic5GUPFBlueprintNGState, UPFBlueCreateModel], Generic[StateTypeVar5GUPF, CreateConfigTypeVar5GUPF]):
    router_needed: bool = True

    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFBlueprintNGState] = StateTypeVar5GUPF):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GUPF:
        return super().state

    @final
    def create(self, create_model: UPFBlueCreateModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.pre_create_upf()
        self.create_upf()
        self.post_create_upf()

    def pre_create_upf(self):
        pass

    @abstractmethod
    def create_upf(self):
        pass

    def post_create_upf(self):
        pass

    @final
    def update(self, create_model: UPFBlueCreateModel):
        self.state.current_config = copy.deepcopy(create_model)
        self.pre_update_upf()
        self.update_upf()
        self.post_update_upf()

    def pre_update_upf(self):
        pass

    @abstractmethod
    def update_upf(self):
        pass

    def post_update_upf(self):
        pass

    @day2_function("/update", [HttpRequestType.PUT])
    def day2_update_upf(self, update_model: UPFBlueCreateModel):
        """
        Update the UPF configuration, note that with some UPF types this may cause additional VMs to be created
        Args:
            update_model: Same model as the create
        """
        if update_model.area_id != self.state.current_config.area_id:
            raise ValueError("Cannot change the area")
        self.update(update_model)

    def get_upfs_info(self) -> List[DeployedUPFInfo]:
        """
        Get information about the UPF(s) deployed by this blueprint
        Returns: List of DeployedUPFInfo
        """
        return copy.copy(self.state.upf_list)

    @abstractmethod
    def add_route_to_router(self, cidr: str, nexthop: str):
        pass

    @abstractmethod
    def deploy_router_blueprint(self) -> Router5GInfo:
        pass

    def update_router_deployment(self):
        if self.router_needed:
            router_info: Router5GInfo
            if not self.create_config.external_router:
                router_info = self.deploy_router_blueprint()
            elif not (self.create_config.external_router.n3_ip and self.create_config.external_router.n6_ip):
                self.logger.debug("At least one of the router's N3 or N6 IPs is not provided, deploying a new router")
                router_info = self.deploy_router_blueprint()
                # If only one of the gateway IPs is provided, override the router's IPs with the provided ones
                if self.create_config.external_router.n3_ip:
                    router_info.network.n3_ip = self.create_config.external_router.n3_ip
                if self.create_config.external_router.n6_ip:
                    router_info.network.n6_ip = self.create_config.external_router.n6_ip
            else:
                # If the router is external and both N3 and N6 IPs are provided, use the provided router info
                router_info = Router5GInfo(
                    blue_id=None,
                    external=True,
                    network=self.create_config.external_router
                )

            self.state.current_config.n3_gateway_ip = router_info.network.n3_ip
            self.state.current_config.n6_gateway_ip = router_info.network.n6_ip
            self.state.current_config.gnb_cidr = router_info.network.gnb_cidr

            self.state.router = router_info

    def update_router_routes(self):
        # The router need to route the traffic for the DNN ip pool through the UPF N6 interface
        if self.router_needed:
            for deployed_upf in self.state.upf_list:
                for slice in deployed_upf.served_slices:
                    for dnn in slice.dnn_list:
                        self.add_route_to_router(dnn.cidr, deployed_upf.network_info.n6_ip.exploded)

    def get_dnn_ip_pool(self, dnn: str) -> str:
        found_ip_pool: Optional[str] = None
        for slice in self.state.current_config.slices:
            for dnnslice in slice.dnn_list:
                if dnnslice.dnn == dnn:
                    if found_ip_pool is None:
                        found_ip_pool = dnnslice.cidr
                    elif found_ip_pool != dnnslice.cidr:
                        raise ValueError("The same dnn for different slices must have the same ip pool")
        if found_ip_pool is None:
            raise ValueError(f"Unable to find ip pool for dnn '{dnn}'")
        return found_ip_pool

    def get_slices_for_dnn(self, dnn: str) -> List[Slice5GWithDNNs]:
        served_slices: List[Slice5GWithDNNs] = []
        for slice in self.state.current_config.slices:
            if dnn in list(map(lambda x: x.dnn, slice.dnn_list)):
                served_slices.append(slice)
        return served_slices
