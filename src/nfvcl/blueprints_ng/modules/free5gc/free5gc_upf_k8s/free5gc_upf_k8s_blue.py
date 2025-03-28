import copy
from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.free5gc import free5gc_default_upf_k8s_config
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import DeployedUPFInfo
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf_k8s import Generic5GUPFK8SBlueprintNG, Generic5GUPFK8SBlueprintNGState
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_models.blueprint_ng.free5gc.free5gcUpfK8s import Free5gcK8sUpfConfig
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo

FREE5GC_UPF_K8S_BLUE_TYPE = "free5gc_upf_k8s"


class Free5gcUpfK8sBlueprintNGState(Generic5GUPFK8SBlueprintNGState):
    upf_values: Optional[Free5gcK8sUpfConfig] = Field(default=None)


@blueprint_type(FREE5GC_UPF_K8S_BLUE_TYPE)
class Free5GCUpfK8s(Generic5GUPFK8SBlueprintNG[Free5gcUpfK8sBlueprintNGState, UPFBlueCreateModel]):

    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFK8SBlueprintNGState] = Free5gcUpfK8sBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create_upf(self):
        self.logger.info("Starting creation of Free5gcUpfK8s blueprint")
        self.state.upf_values = copy.deepcopy(free5gc_default_upf_k8s_config.default_upfk8s_config)

        upf_helm_chart = HelmChartResource(
            area=self.state.current_config.area_id,
            name=f"free5gc-upf",
            chart="helm_charts/charts/free5gc-upf-4.0.0.tgz",
            chart_as_path=True,
            namespace=self.id
        )
        self.register_resource(upf_helm_chart)

        self.state.helm_chart_resources[upf_helm_chart.id] = upf_helm_chart

        if self.state.current_config.networks.n4.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n4 = self.provider.reserve_k8s_multus_ip(upf_helm_chart.area, self.state.current_config.networks.n4.net_name)
        if self.state.current_config.networks.n3.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n3 = self.provider.reserve_k8s_multus_ip(upf_helm_chart.area, self.state.current_config.networks.n3.net_name)
        if self.state.current_config.networks.n6.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n6 = self.provider.reserve_k8s_multus_ip(upf_helm_chart.area, self.state.current_config.networks.n6.net_name)

        self.update_upf_values()
        self.provider.install_helm_chart(upf_helm_chart, self.state.upf_values.model_dump(exclude_none=True, by_alias=True))
        self.update_upf_info()

    def update_upf_values(self):
        if self.state.multus_network_info.n4:
            self.state.upf_values.global_.n4network.set_multus(True, self.state.multus_network_info.n4)
            self.state.upf_values.upf.n4if.ip_address = self.state.multus_network_info.n4.ip_address.exploded
        if self.state.multus_network_info.n3:
            self.state.upf_values.global_.n3network.set_multus(True, self.state.multus_network_info.n3)
            self.state.upf_values.upf.n3if.ip_address = self.state.multus_network_info.n3.ip_address.exploded
        if self.state.multus_network_info.n6:
            self.state.upf_values.global_.n6network.set_multus(True, self.state.multus_network_info.n6)
            self.state.upf_values.upf.n6if.ip_address = self.state.multus_network_info.n6.ip_address.exploded

        # Clearing previous config
        self.state.upf_values.upf.configuration.dnn_list.clear()

        for new_slice in self.state.current_config.slices:
            for dnn in new_slice.dnn_list:
                self.state.upf_values.upf.configuration.dnn_list.append(dnn)
                self.state.upf_values.global_.uesubnet.append(dnn.cidr)

        self.state.upf_values.upf.name = f"upf{self.state.current_config.area_id}"

    def update_upf(self):
        """
        Update the UPF configuration
        """
        self.update_upf_values()
        self.provider.update_values_helm_chart(next(iter(self.state.helm_chart_resources.values())), self.state.upf_values.model_dump(exclude_none=True, by_alias=True))
        self.update_upf_info()

    def update_upf_info(self):
        # TODO fix support for Load Balancer
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
