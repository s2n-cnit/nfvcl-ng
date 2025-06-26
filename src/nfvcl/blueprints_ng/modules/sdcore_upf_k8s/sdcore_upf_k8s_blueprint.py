import copy
from typing import Optional, List, Dict

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import DeployedUPFInfo
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf_k8s import Generic5GUPFK8SBlueprintNGState, Generic5GUPFK8SBlueprintNG
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf_vm import Router5GInfo
from nfvcl.blueprints_ng.modules.sdcore_upf_k8s import sdcore_default_upf_k8s_config
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo
from nfvcl_models.blueprint_ng.sdcore.sdcoreUpfK8s import SdcoreK8sUpfConfig

SDCORE_UPF_K8S_BLUE_TYPE = "sdcore_upf_k8s"


class SdCoreUPFK8sBlueprintNGState(Generic5GUPFK8SBlueprintNGState):
    upf_values: Optional[SdcoreK8sUpfConfig] = Field(default=None)
    currently_deployed_dnns: Dict[str, DeployedUPFInfo] = Field(default_factory=dict)
    router: Optional[Router5GInfo] = Field(default=None)


@blueprint_type(SDCORE_UPF_K8S_BLUE_TYPE)
class SdCoreUPFK8SBlueprintNG(Generic5GUPFK8SBlueprintNG[SdCoreUPFK8sBlueprintNGState, UPFBlueCreateModel]):
    router_needed = True

    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFK8SBlueprintNGState] = SdCoreUPFK8sBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_upf(self):
        self.update_deployments()

    def spawn_upf(self, dnn: str):
        self.logger.info(f"Starting creation of SdCoreK8sBlueprintNG blueprint for dnn: {dnn}")
        self.state.upf_values = copy.deepcopy(sdcore_default_upf_k8s_config.default_sdcore_upfk8s_config)

        upf_helm_chart = HelmChartResource(
            area=self.state.current_config.area_id,
            name=f"sdcore-upf",
            chart="helm_charts/charts/bess-upf-1.0.0.tgz",
            chart_as_path=True,
            namespace=self.id
        )
        self.register_resource(upf_helm_chart)

        self.state.helm_chart_resources[upf_helm_chart.id] = upf_helm_chart

        if self.state.current_config.networks.n4.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n4 = self.provider.reserve_k8s_multus_ip(upf_helm_chart.area, self.state.current_config.networks.n4.net_name)
            self.state.upf_values.config.upf.n4.set_multus(self.state.multus_network_info.n4)
        if self.state.current_config.networks.n3.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n3 = self.provider.reserve_k8s_multus_ip(upf_helm_chart.area, self.state.current_config.networks.n3.net_name)
            self.state.upf_values.config.upf.access.set_multus(self.state.multus_network_info.n3, self.state.current_config.n3_gateway_ip.exploded)
        if self.state.current_config.networks.n6.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n6 = self.provider.reserve_k8s_multus_ip(upf_helm_chart.area, self.state.current_config.networks.n6.net_name)
            self.state.upf_values.config.upf.core.set_multus(self.state.multus_network_info.n6, self.state.current_config.n6_gateway_ip.exploded)

        self.state.upf_values.config.upf.cfg_files.upf_jsonc.cpiface.dnn = dnn
        self.state.upf_values.config.upf.enb.subnet = self.state.current_config.gnb_cidr.exploded
        ue_ip_pool = self.get_dnn_ip_pool(dnn)
        self.state.upf_values.config.upf.cfg_files.upf_jsonc.cpiface.ue_ip_pool = ue_ip_pool
        # self.state.upf_values.config.upf.cfg_files.upf_jsonc.cpiface.hostname = f"upf-{self.state.current_config.area_id}-{dnn}"

        self.add_route_to_router(ue_ip_pool, self.state.multus_network_info.n6.ip_address.exploded)
        self.provider.install_helm_chart(upf_helm_chart, self.state.upf_values.model_dump(exclude_none=True, by_alias=True))

        return DeployedUPFInfo(
            area=self.state.current_config.area_id,
            served_slices=self.get_slices_for_dnn(dnn),
            vm_resource_id=None,
            vm_configurator_id=None,
            helm_chart_resource_id=upf_helm_chart.id,
            network_info=UPFNetworkInfo(
                n4_cidr=self.state.multus_network_info.n4.network_cidr if self.state.multus_network_info.n4 else SerializableIPv4Network("1.1.1.1/32"),
                n3_cidr=self.state.multus_network_info.n3.network_cidr if self.state.multus_network_info.n3 else SerializableIPv4Network("1.1.1.1/32"),
                n6_cidr=self.state.multus_network_info.n6.network_cidr if self.state.multus_network_info.n6 else SerializableIPv4Network("1.1.1.1/32"),
                n4_ip=self.state.multus_network_info.n4.ip_address if self.state.multus_network_info.n4 else SerializableIPv4Address("1.1.1.1"),
                n3_ip=self.state.multus_network_info.n3.ip_address if self.state.multus_network_info.n3 else SerializableIPv4Address("1.1.1.1"),
                n6_ip=self.state.multus_network_info.n6.ip_address if self.state.multus_network_info.n6 else SerializableIPv4Address("1.1.1.1")
            )
        )

    def stop_upf(self, dnn: str):
        self.logger.info(f"Stopping SdCoreK8sBlueprintNG blueprint for dnn: {dnn}")
        upf_info = self.state.currently_deployed_dnns[dnn]

        self.provider.uninstall_helm_chart(self.state.helm_chart_resources[upf_info.helm_chart_resource_id])
        self.deregister_resource(self.state.helm_chart_resources[upf_info.helm_chart_resource_id])
        self.logger.info(f"SdCoreK8sBlueprintNG blueprint dnn: {dnn} stopped")

        return upf_info

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
                deployed_info = self.spawn_upf(dnn)
                self.state.upf_list.append(deployed_info)
                self.state.currently_deployed_dnns[dnn] = deployed_info
        dnn_to_undeploy = set(self.state.currently_deployed_dnns) - set(dnns_to_deploy)
        for dnn in set(dnn_to_undeploy):
            deployed_info = self.stop_upf(dnn)
            self.state.upf_list.remove(deployed_info)
            del self.state.currently_deployed_dnns[dnn]

    def update_upf_info(self):
        deployed_upf_info = DeployedUPFInfo(
            area=self.state.current_config.area_id,
            served_slices=self.state.current_config.slices,
            vm_resource_id=None,
            vm_configurator_id=None,
            network_info=UPFNetworkInfo(
                n4_cidr=self.state.multus_network_info.n4.network_cidr if self.state.multus_network_info.n4 else SerializableIPv4Network("1.1.1.1/32"),
                n3_cidr=self.state.multus_network_info.n3.network_cidr if self.state.multus_network_info.n3 else SerializableIPv4Network("1.1.1.1/32"),
                n6_cidr=self.state.multus_network_info.n6.network_cidr if self.state.multus_network_info.n6 else SerializableIPv4Network("1.1.1.1/32"),
                n4_ip=self.state.multus_network_info.n4.ip_address if self.state.multus_network_info.n4 else SerializableIPv4Address("1.1.1.1"),
                n3_ip=self.state.multus_network_info.n3.ip_address if self.state.multus_network_info.n3 else SerializableIPv4Address("1.1.1.1"),
                n6_ip=self.state.multus_network_info.n6.ip_address if self.state.multus_network_info.n6 else SerializableIPv4Address("1.1.1.1")
            )
        )
        self.state.upf_list.clear()
        self.state.upf_list.append(deployed_upf_info)
