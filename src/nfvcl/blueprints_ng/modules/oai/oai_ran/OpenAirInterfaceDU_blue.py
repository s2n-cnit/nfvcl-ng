import copy
from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_du_k8s import Generic5GDUK8sBlueprintNGState, Generic5GDUK8sBlueprintNG
from nfvcl.blueprints_ng.modules.oai import oai_default_du_config
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.core5g.OAI_Models import DU
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_models.blueprint_ng.g5.ran import DUBlueCreateModel
from nfvcl_models.blueprint_ng.g5.ue import USRPType

OAI_DU_BLUE_TYPE = "oai_du"


class OAIDuBlueprintNGState(Generic5GDUK8sBlueprintNGState):
    oai_du_config_values: Optional[DU] = Field(default=None)


@blueprint_type(OAI_DU_BLUE_TYPE)
class OpenAirInterfaceDu(Generic5GDUK8sBlueprintNG[OAIDuBlueprintNGState, DUBlueCreateModel]):

    def get_svc_name(self) -> str:
        return "oai-ran-lb"

    def __init__(self, blueprint_id: str, state_type: type[Generic5GDUK8sBlueprintNGState] = OAIDuBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_du(self):
        self.logger.info("Starting creation of Open Air Interface DU blueprint")

        self.state.oai_du_config_values = copy.deepcopy(oai_default_du_config.default_du_config)

        # self.state.current_config = create_model
        self.state.du_helm_chart = HelmChartResource(
            area=self.state.current_config.area_id,
            name="du",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/oai-du-2.1.0.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.du_helm_chart)

        if self.state.current_config.networks.f1.type == NetworkEndPointType.MULTUS:
            net_f1 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.f1.net_name)
            self.state.oai_du_config_values.multus.f1_interface.set_multus(True, net_f1, self.state.current_config.networks.f1.routes)
            self.state.oai_du_config_values.config.f1_if_name = "f1"

        if self.state.current_config.networks.ru1.type == NetworkEndPointType.MULTUS:
            net_ru1 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.ru1.net_name)
            self.state.oai_du_config_values.multus.ru1_interface.set_multus(True, net_ru1, self.state.current_config.networks.ru1.routes)

        if self.state.current_config.networks.ru2.type == NetworkEndPointType.MULTUS:
            net_ru2 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.ru2.net_name)
            self.state.oai_du_config_values.multus.ru2_interface.set_multus(True, net_ru2, self.state.current_config.networks.ru2.routes)

        self.state.oai_du_config_values.config.f1du_port = self.state.current_config.f1_port
        self.state.oai_du_config_values.config.f1cu_port = self.state.current_config.f1_port

        self.update_du_values()

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.du_helm_chart,
            self.state.oai_du_config_values.model_dump(exclude_none=True, by_alias=True)
        )

    def update_du_values(self):
        self.state.oai_du_config_values.config.mcc = self.state.current_config.mcc
        self.state.oai_du_config_values.config.mnc = self.state.current_config.mnc
        self.state.oai_du_config_values.config.tac = str(self.state.current_config.tac)
        self.state.oai_du_config_values.config.snssai_list = self.state.current_config.snssai_list
        self.state.oai_du_config_values.config.usrp = self.state.current_config.usrp
        self.state.oai_du_config_values.config.cu_host = self.state.current_config.cu_host
        self.state.oai_du_config_values.config.gnb_id = f'0x{self.state.current_config.gnb_id:0>4x}'

        additional_options = "--sa --log_config.global_log_options level,nocolor,time"

        if self.state.current_config.usrp == USRPType.RFSIM:
            self.state.oai_du_config_values.config.use_additional_options = f"{additional_options} --rfsim"
        else:
            self.state.oai_du_config_values.config.use_additional_options = additional_options

    def update_du(self):
        self.update_du_values()
        self.provider.update_values_helm_chart(
            self.state.du_helm_chart,
            self.state.oai_du_config_values.model_dump(exclude_none=True, by_alias=True)
        )
