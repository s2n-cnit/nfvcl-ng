import copy
from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_gnb_k8s import Generic5GGNBK8sBlueprintNGState, Generic5GGNBK8sBlueprintNG
from nfvcl.blueprints_ng.modules.oai import oai_default_gnb_config
from nfvcl_models.blueprint_ng.core5g.OAI_Models import GNB
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_models.blueprint_ng.g5.ran import GNBBlueCreateModel
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.g5.ue import USRPType

OAI_GNB_BLUE_TYPE = "oai_gnb"


class OAIGnbBlueprintNGState(Generic5GGNBK8sBlueprintNGState):
    oai_gnb_config_values: Optional[GNB] = Field(default=None)
    gnb_helm_chart: Optional[HelmChartResource] = Field(default=None)


@blueprint_type(OAI_GNB_BLUE_TYPE)
class OpenAirInterfaceGnb(Generic5GGNBK8sBlueprintNG[OAIGnbBlueprintNGState, GNBBlueCreateModel]):

    def get_svc_name(self) -> str:
        return "oai-ran-lb"

    def __init__(self, blueprint_id: str, state_type: type[Generic5GGNBK8sBlueprintNGState] = OAIGnbBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_gnb(self):
        self.logger.info("Starting creation of Open Air Interface GNB blueprint")

        self.state.oai_gnb_config_values = copy.deepcopy(oai_default_gnb_config.default_gnb_config)

        # self.state.current_config = create_model
        self.state.gnb_helm_chart = HelmChartResource(
            area=self.state.current_config.area_id,
            name="gnb",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/oai-gnb-2.1.0.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.gnb_helm_chart)

        if self.state.current_config.networks.n2.type == NetworkEndPointType.MULTUS:
            net_n2 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.n2.net_name)
            self.state.oai_gnb_config_values.multus.n2_interface.set_multus(True, net_n2, self.state.current_config.networks.n2.routes)
            self.state.oai_gnb_config_values.config.n2_if_name = "n2"

        if self.state.current_config.networks.n3.type == NetworkEndPointType.MULTUS:
            net_n3 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.n3.net_name)
            self.state.oai_gnb_config_values.multus.n3_interface.set_multus(True, net_n3, self.state.current_config.networks.n3.routes)
            self.state.oai_gnb_config_values.config.n3_if_name = "n3"

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
        self.state.oai_gnb_config_values.config.tac = str(self.state.current_config.tac)
        self.state.oai_gnb_config_values.config.snssai_list = self.state.current_config.snssai_list
        self.state.oai_gnb_config_values.config.usrp = self.state.current_config.usrp
        self.state.oai_gnb_config_values.config.gnb_id = f'0x{self.state.current_config.gnb_id:0>4x}'
        self.state.oai_gnb_config_values.config.amf_ip_address = self.state.current_config.amf

        additional_options = "--sa --log_config.global_log_options level,nocolor,time"

        if self.state.current_config.usrp == USRPType.RFSIM:
            self.state.oai_gnb_config_values.config.use_additional_options = f"{additional_options} --rfsim"
        else:
            self.state.oai_gnb_config_values.config.use_additional_options = additional_options

        routes_list = []
        for route in self.state.current_config.additional_routes:
            tmp = route.as_linux_replace_command()
            if tmp not in routes_list:
                routes_list.append(tmp)
        self.state.oai_gnb_config_values.config.additional_routes = routes_list

    def update_gnb(self):
        self.update_gnb_values()
        self.provider.update_values_helm_chart(
            self.state.gnb_helm_chart,
            self.state.oai_gnb_config_values.model_dump(exclude_none=True, by_alias=True)
        )
        self.logger.info("Restarting GNB")
        self.provider.restart_all_deployments(self.state.gnb_helm_chart, self.id)

    def restart_gnb(self):
        self.logger.info("Restarting GNB")
        self.provider.restart_all_deployments(self.state.gnb_helm_chart, self.id)

