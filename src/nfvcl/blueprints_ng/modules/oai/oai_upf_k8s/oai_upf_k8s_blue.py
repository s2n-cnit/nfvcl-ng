import copy
from typing import Optional

from nfvcl_core_models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address
from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import DeployedUPFInfo
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf_k8s import Generic5GUPFK8SBlueprintNG, Generic5GUPFK8SBlueprintNGState
from nfvcl.blueprints_ng.modules.oai import oai_default_upf_config
from nfvcl.blueprints_ng.modules.oai import oai_utils
from nfvcl_models.blueprint_ng.core5g.OAI_Models import OaiUpfValuesModel, AvailableSmf, Snssai, DnnItem
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.resources import HelmChartResource

OAI_UPF_K8S_BLUE_TYPE = "oai_upf_k8s"


class OAIUpfK8sBlueprintNGState(Generic5GUPFK8SBlueprintNGState):
    upf_values: Optional[OaiUpfValuesModel] = Field(default=None)

@blueprint_type(OAI_UPF_K8S_BLUE_TYPE)
class OpenAirInterfaceUpfK8s(Generic5GUPFK8SBlueprintNG[OAIUpfK8sBlueprintNGState, UPFBlueCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFK8SBlueprintNGState] = OAIUpfK8sBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_upf(self):
        self.logger.info("Starting creation of OpenAirInterfaceUpfK8s blueprint")
        self.state.upf_values = copy.deepcopy(oai_default_upf_config.default_upf_config)

        upf_helm_chart = HelmChartResource(
            area=self.state.current_config.area_id,
            name=f"oai-upf",
            chart="helm_charts/charts/oai-upf-2.1.0.tgz",
            chart_as_path=True,
            namespace=self.id
        )
        self.register_resource(upf_helm_chart)

        self.state.helm_chart_resources[upf_helm_chart.id] = upf_helm_chart

        self.allocate_ips(upf_helm_chart)
        self.update_upf_values()
        self.provider.install_helm_chart(upf_helm_chart, self.state.upf_values.model_dump(exclude_none=True, by_alias=True))
        self.update_upf_info()

    def allocate_ips(self, upf_helm_chart: HelmChartResource):
        if self.state.current_config.networks.n4.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n4 = self.provider.reserve_k8s_multus_ip(upf_helm_chart.area, self.state.current_config.networks.n4.net_name)
        if self.state.current_config.networks.n3.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n3 = self.provider.reserve_k8s_multus_ip(upf_helm_chart.area, self.state.current_config.networks.n3.net_name)
        if self.state.current_config.networks.n6.type == NetworkEndPointType.MULTUS:
            self.state.multus_network_info.n6 = self.provider.reserve_k8s_multus_ip(upf_helm_chart.area, self.state.current_config.networks.n6.net_name)

    def update_upf_values(self):
        """
        Update the UPF configuration
        """

        if self.state.multus_network_info.n4:
            self.state.upf_values.multus.n4Interface.set_multus(True, self.state.multus_network_info.n4)
        if self.state.multus_network_info.n3:
            self.state.upf_values.multus.n3Interface.set_multus(True, self.state.multus_network_info.n3)
        if self.state.multus_network_info.n6:
            self.state.upf_values.multus.n6Interface.set_multus(True, self.state.multus_network_info.n6)

        # Clearing previous config
        self.state.upf_values.upfconfig.snssais.clear()
        self.state.upf_values.upfconfig.upf.upf_info.sNssaiUpfInfoList.clear()
        self.state.upf_values.upfconfig.dnns.clear()

        self.state.upf_values.upfconfig.nfs.upf.host = f"oai-upf{self.state.current_config.area_id}"
        self.state.upf_values.upfconfig.nfs.upf.sbi.interface_name = "eth0"
        self.state.upf_values.upfconfig.nfs.upf.n3.interface_name = "n3" if self.state.multus_network_info.n3 else "eth0"
        self.state.upf_values.upfconfig.nfs.upf.n4.interface_name = "n4" if self.state.multus_network_info.n4 else "eth0"
        self.state.upf_values.upfconfig.nfs.upf.n6.interface_name = "n6" if self.state.multus_network_info.n6 else "eth0"
        self.state.upf_values.upfconfig.nfs.upf.n9.interface_name = "eth0"

        self.state.upf_values.upfconfig.nfs.nrf.host = f"oai-nrf-svc-lb.{self.base_model.parent_blue_id}" #svc.cluster.local"

        if self.state.current_config.smf_ip:
            self.state.upf_values.upfconfig.upf.smfs = [AvailableSmf(host=self.state.current_config.smf_ip.exploded)]

        self.state.upf_values.upfconfig.upf.remote_n6_gw = self.state.multus_network_info.n6.gateway_ip.exploded if self.state.multus_network_info.n6 and self.state.multus_network_info.n6.gateway_ip else "127.0.0.1"

        for new_slice in self.state.current_config.slices:
            new_snssai: Snssai = oai_utils.add_snssai(self.state.upf_values.upfconfig, new_slice.sd, new_slice.sst)
            for dnn in new_slice.dnn_list:
                dnn_item = DnnItem(
                    dnn=dnn.dnn
                )
                # Add DNNS
                oai_utils.add_dnn_dnns(self.state.upf_values.upfconfig, dnn.dnn, dnn.cidr)
                oai_utils.add_dnn_snssai_upf_info_list_item(self.state.upf_values.upfconfig, new_snssai, dnn_item)

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
                n4_ip=self.state.multus_network_info.n4.ip_address if self.state.multus_network_info.n6 else SerializableIPv4Address("1.1.1.1"),
                n3_ip=self.state.multus_network_info.n3.ip_address if self.state.multus_network_info.n6 else SerializableIPv4Address("1.1.1.1"),
                n6_ip=self.state.multus_network_info.n6.ip_address if self.state.multus_network_info.n6 else SerializableIPv4Address("1.1.1.1")
            )
        )
        self.state.upf_list.clear()
        self.state.upf_list.append(deployed_upf_info)
