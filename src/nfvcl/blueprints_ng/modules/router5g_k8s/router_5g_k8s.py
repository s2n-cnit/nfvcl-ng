import copy
import re
from typing import Optional, Dict

from pydantic import Field

from nfvcl.blueprints_ng.modules.router5g_k8s import router5g_default_k8s_config
from nfvcl.blueprints_ng.modules.router_5g.router_5g import Router5GCreateModel, Router5GAddRouteModel
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.blueprints.blueprint import BlueprintNGState
from nfvcl_core_models.http_models import HttpRequestType
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address, SerializableIPv4Network
from nfvcl_core_models.network.network_models import MultusInterface
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.core5g.common import Router5GNetworkInfo, NetworkEndPointType
from nfvcl_models.blueprint_ng.router_5g.router5gK8s import Router5GK8s, Interface, Route


class K8sRouterMultusNetworkInfo(NFVCLBaseModel):
    n4: Optional[MultusInterface] = Field(default=None)
    n3: Optional[MultusInterface] = Field(default=None)
    n6: Optional[MultusInterface] = Field(default=None)
    gnb: Optional[MultusInterface] = Field(default=None)


class Router5GK8sBlueprintNGState(BlueprintNGState):
    current_config: Optional[Router5GCreateModel] = Field(default=None)
    router_values: Optional[Router5GK8s] = Field(default=None)
    router_chart_resources: Optional[HelmChartResource] = Field(default=None)
    multus_network_info: K8sRouterMultusNetworkInfo = Field(default_factory=K8sRouterMultusNetworkInfo)


@blueprint_type("router_5g_k8s")
class Router5GK8sBlueprintNG(BlueprintNG[Router5GK8sBlueprintNGState, Router5GCreateModel]):

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = Router5GK8sBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: Router5GCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of Router5GBlueprintNG blueprint")
        self.state.router_values = copy.deepcopy(router5g_default_k8s_config.default_sdcore_routerk8s_config)

        self.state.router_chart_resources = HelmChartResource(
            area=create_model.area_id,
            name=f"router5g",
            chart="helm_charts/charts/router-0.1.1.tgz",
            chart_as_path=True,
            namespace=self.id
        )
        self.register_resource(self.state.router_chart_resources)

        if create_model.networks.n3.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n3 = self.provider.reserve_k8s_multus_ip(self.state.router_chart_resources.area, create_model.networks.n3.net_name)
            self.state.router_values.config.router.interfaces.append(
                Interface(
                    name="access",
                    ip=f"{self.state.multus_network_info.n3.ip_address}/{self.state.multus_network_info.n3.prefixlen}",
                    iface=self.state.multus_network_info.n3.host_interface
                )
            )
        if create_model.networks.n6.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n6 = self.provider.reserve_k8s_multus_ip(self.state.router_chart_resources.area, create_model.networks.n6.net_name)
            self.state.router_values.config.router.interfaces.append(
                Interface(
                    name="core",
                    ip=f"{self.state.multus_network_info.n6.ip_address}/{self.state.multus_network_info.n6.prefixlen}",
                    iface=self.state.multus_network_info.n6.host_interface
                )
            )
        if create_model.networks.gnb.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.gnb = self.provider.reserve_k8s_multus_ip(self.state.router_chart_resources.area, create_model.networks.gnb.net_name)
            self.state.router_values.config.router.interfaces.append(
                Interface(
                    name="ran",
                    ip=f"{self.state.multus_network_info.gnb.ip_address}/{self.state.multus_network_info.gnb.prefixlen}",
                    iface=self.state.multus_network_info.gnb.host_interface
                )
            )

        self.provider.install_helm_chart(self.state.router_chart_resources, self.state.router_values.model_dump(exclude_none=True, by_alias=True))

    # def a(self):
    #     if self.state.multus_network_info.n3:
    #         self.state.router_values.config.router.interfaces.append(
    #             Interface(
    #                 name="access",
    #                 ip=f"{self.state.multus_network_info.n3.ip_address}/{self.state.multus_network_info.n3.prefixlen}",
    #                 iface=self.state.multus_network_info.n3.host_interface
    #             )
    #         )
    #     if self.state.multus_network_info.n6:
    #         self.state.router_values.config.router.interfaces.append(
    #             Interface(
    #                 name="core",
    #                 ip=f"{self.state.multus_network_info.n6.ip_address}/{self.state.multus_network_info.n6.prefixlen}",
    #                 iface=self.state.multus_network_info.n6.host_interface
    #             )
    #         )
    #     if self.state.multus_network_info.gnb:
    #         self.state.router_values.config.router.interfaces.append(
    #             Interface(
    #                 name="ran",
    #                 ip=f"{self.state.multus_network_info.gnb.ip_address}/{self.state.multus_network_info.gnb.prefixlen}",
    #                 iface=self.state.multus_network_info.gnb.host_interface
    #             )
    #         )

    def update_router_values(self):
        self.provider.update_values_helm_chart(
            self.state.router_chart_resources,
            self.state.router_values.model_dump(exclude_none=True, by_alias=True)
        )

    @day2_function("/add_routes", [HttpRequestType.PUT])
    def add_routes(self, model: Router5GAddRouteModel):
        for route in model.additional_routes:
            tmp = Route(to=route.network_cidr, via=route.next_hop)
            if tmp not in self.state.router_values.config.router.routes:
                self.state.router_values.config.router.routes.append(tmp)
        self.update_router_values()


    def get_router_info(self) -> Router5GNetworkInfo:
        return Router5GNetworkInfo(
            n3_ip=SerializableIPv4Address(self.state.multus_network_info.n3.ip_address),
            n6_ip=SerializableIPv4Address(self.state.multus_network_info.n6.ip_address),
            gnb_ip=SerializableIPv4Address(self.state.multus_network_info.gnb.ip_address),
            gnb_cidr=SerializableIPv4Network(self.state.multus_network_info.gnb.network_cidr)
        )
