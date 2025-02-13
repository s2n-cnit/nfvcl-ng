import copy
from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.oai import oai_default_ue_config
from nfvcl.models.blueprint_ng.core5g.OAI_Models import OAIUE
from nfvcl.models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_core.models.resources import HelmChartResource

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_ue import Generic5GUEBlueprintNGState, Generic5GUEBlueprintNG
from nfvcl.models.blueprint_ng.g5.ue import UEBlueCreateModelGeneric, USRPType
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type

OAI_UE_BLUE_TYPE = "oai_ue"


class OAIUEBlueprintNGState(Generic5GUEBlueprintNGState):
    oai_ue_config_values: Optional[OAIUE] = Field(default=None)
    ue_helm_chart: Optional[HelmChartResource] = Field(default=None)


@blueprint_type(OAI_UE_BLUE_TYPE)
class OpenAirInterfaceUE(Generic5GUEBlueprintNG[OAIUEBlueprintNGState, UEBlueCreateModelGeneric]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GUEBlueprintNGState] = OAIUEBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_ue(self):
        self.logger.info("Starting creation of Open Air Interface UE blueprint")
        self.state.oai_ue_config_values = copy.deepcopy(oai_default_ue_config.default_oai_ue_config)

        self.state.ue_helm_chart = HelmChartResource(
            area=self.state.current_config.area_id,
            name="oai-ue",
            chart="helm_charts/charts/oai-nr-ue-2.1.0.tgz",
            chart_as_path=True,
            namespace=self.id
        )
        self.register_resource(self.state.ue_helm_chart)

        if self.state.current_config.networks.ru1.type == NetworkEndPointType.MULTUS:
            net_radio = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.ru1.net_name)
            self.state.oai_ue_config_values.multus.set_multus(True, net_radio, self.state.current_config.networks.ru1.routes)

        self.update_ue_values()

        self.provider.install_helm_chart(
            self.state.ue_helm_chart,
            self.state.oai_ue_config_values.model_dump(exclude_none=True, by_alias=True)
        )

    def update_ue_values(self):
        self.state.oai_ue_config_values.config.rf_sim_server = self.state.current_config.gnb_host
        self.state.oai_ue_config_values.config.full_imsi = self.state.current_config.sims[0].imsi
        self.state.oai_ue_config_values.config.full_key = self.state.current_config.sims[0].key
        self.state.oai_ue_config_values.config.opc = self.state.current_config.sims[0].op
        self.state.oai_ue_config_values.config.dnn = self.state.current_config.sims[0].sessions[0].apn
        self.state.oai_ue_config_values.config.sst = str(self.state.current_config.sims[0].sessions[0].slice.sst)
        self.state.oai_ue_config_values.config.sd = str(self.state.current_config.sims[0].sessions[0].slice.sd)
        self.state.oai_ue_config_values.config.usrp = self.state.current_config.usrp

        additional_options = "--sa -r 106 --numerology 1 -C 3619200000 --log_config.global_log_options level,nocolor,time"

        if self.state.current_config.usrp == USRPType.RFSIM:
            self.state.oai_ue_config_values.config.use_additional_options = f"{additional_options} --rfsim"
        else:
            self.state.oai_ue_config_values.config.use_additional_options = additional_options

    def update_ue(self):
        self.update_ue_values()
        self.provider.update_values_helm_chart(
            self.state.ue_helm_chart,
            self.state.oai_ue_config_values.model_dump(exclude_none=True, by_alias=True)
        )
