import copy
from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_gnb import Generic5GGNBBlueprintNGState, Generic5GGNBBlueprintNG
from nfvcl.blueprints_ng.modules.oai import oai_default_gnb_config
from nfvcl.models.blueprint_ng.core5g.OAI_Models import GNB
from nfvcl.models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl.models.blueprint_ng.g5.ran import GNBBlueCreateModel
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core.models.resources import HelmChartResource

OAI_GNB_BLUE_TYPE = "oai_gnb"


class OAIGnbBlueprintNGState(Generic5GGNBBlueprintNGState):
    oai_gnb_config_values: Optional[GNB] = Field(default=None)
    gnb_helm_chart: Optional[HelmChartResource] = Field(default=None)


@blueprint_type(OAI_GNB_BLUE_TYPE)
class OpenAirInterfaceGnb(Generic5GGNBBlueprintNG[OAIGnbBlueprintNGState, GNBBlueCreateModel]):

    def __init__(self, blueprint_id: str, state_type: type[Generic5GGNBBlueprintNGState] = OAIGnbBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_gnb(self):
        self.logger.info("Starting creation of Open Air Interface GNB blueprint")

        self.state.oai_gnb_config_values = copy.deepcopy(oai_default_gnb_config.default_gnb_config)

        # self.state.current_config = create_model
        self.state.gnb_helm_chart = HelmChartResource(
            area=self.state.current_config.area_id,
            name="gnb",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/oai5grangnb-2.1.0.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.gnb_helm_chart)

        if self.state.current_config.networks.n2.type == NetworkEndPointType.MULTUS:
            net_n2 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.n2.net_name)
            self.state.oai_gnb_config_values.multus.n2_interface.set_multus(True, net_n2, self.state.current_config.networks.n2.routes)

        if self.state.current_config.networks.n3.type == NetworkEndPointType.MULTUS:
            net_n3 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.n3.net_name)
            self.state.oai_gnb_config_values.multus.n3_interface.set_multus(True, net_n3, self.state.current_config.networks.n3.routes)

        if self.state.current_config.networks.ru1.type == NetworkEndPointType.MULTUS:
            net_ru1 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.ru1.net_name)
            self.state.oai_gnb_config_values.multus.ru1_interface.set_multus(True, net_ru1, self.state.current_config.networks.ru1.routes)

        if self.state.current_config.networks.ru2.type == NetworkEndPointType.MULTUS:
            net_ru2 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.ru2.net_name)
            self.state.oai_gnb_config_values.multus.ru2_interface.set_multus(True, net_ru2, self.state.current_config.networks.ru2.routes)

        self.update_gnb_values()

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.gnb_helm_chart,
            self.state.oai_gnb_config_values.model_dump(exclude_none=True, by_alias=True)
        )

    def update_gnb_values(self):
        self.state.oai_gnb_config_values.config.mcc = self.state.current_config.mcc
        self.state.oai_gnb_config_values.config.mnc = self.state.current_config.mnc
        self.state.oai_gnb_config_values.config.tac = self.state.current_config.tac
        self.state.oai_gnb_config_values.config.sst = self.state.current_config.sst
        self.state.oai_gnb_config_values.config.sd = self.state.current_config.sd
        self.state.oai_gnb_config_values.config.usrp = self.state.current_config.usrp
        if self.state.current_config.amf:
            self.state.oai_gnb_config_values.config.amf_ip_address = self.state.current_config.amf

    def update_gnb(self):
        self.update_gnb_values()
        self.provider.update_values_helm_chart(
            self.state.gnb_helm_chart,
            self.state.oai_gnb_config_values.model_dump(exclude_none=True, by_alias=True)
        )
