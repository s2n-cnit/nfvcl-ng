import copy
from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_cucp_k8s import Generic5GCUCPK8sBlueprintNG, Generic5GCUCPK8sBlueprintNGState
from nfvcl.blueprints_ng.modules.oai import oai_default_cu_cp_config
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.core5g.OAI_Models import CUCP
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_models.blueprint_ng.g5.ran import CUCPBlueCreateModel

OAI_CUCP_BLUE_TYPE = "oai_cu-cp"


class OAICucpBlueprintNGState(Generic5GCUCPK8sBlueprintNGState):
    oai_cucp_config_values: Optional[CUCP] = Field(default=None)
    cucp_helm_chart: Optional[HelmChartResource] = Field(default=None)


@blueprint_type(OAI_CUCP_BLUE_TYPE)
class OpenAirInterfaceCucp(Generic5GCUCPK8sBlueprintNG[OAICucpBlueprintNGState, CUCPBlueCreateModel]):

    def get_svc_name(self) -> str:
        return "oai_cu-lb"

    def __init__(self, blueprint_id: str, state_type: type[Generic5GCUCPK8sBlueprintNGState] = OAICucpBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_cucp(self):
        self.logger.info("Starting creation of Open Air Interface CUCP blueprint")

        self.state.oai_cucp_config_values = copy.deepcopy(oai_default_cu_cp_config.default_cucp_config)

        # self.state.current_config = create_model
        self.state.cucp_helm_chart = HelmChartResource(
            area=self.state.current_config.area_id,
            name="cucp",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/oai-cu-cp-2.1.0.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.cucp_helm_chart)

        if self.state.current_config.networks.n2.type == NetworkEndPointType.MULTUS:
            net_n2 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.n2.net_name)
            self.state.oai_cucp_config_values.multus.n2_interface.set_multus(True, net_n2, self.state.current_config.networks.n2.routes)
            self.state.oai_cucp_config_values.config.n2_if_name = "n2"

        if self.state.current_config.networks.e1.type == NetworkEndPointType.MULTUS:
            net_e1 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.e1.net_name)
            self.state.oai_cucp_config_values.multus.e1_interface.set_multus(True, net_e1, self.state.current_config.networks.e1.routes)
            self.state.oai_cucp_config_values.config.e1_if_name = "e1"

        if self.state.current_config.networks.f1.type == NetworkEndPointType.MULTUS:
            net_f1 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.f1.net_name)
            self.state.oai_cucp_config_values.multus.f1c_interface.set_multus(True, net_f1, self.state.current_config.networks.f1.routes)
            self.state.oai_cucp_config_values.config.f1_if_name = "f1c"

        self.state.oai_cucp_config_values.config.f1du_port = self.state.current_config.f1_port
        self.state.oai_cucp_config_values.config.f1cu_port = self.state.current_config.f1_port

        self.update_cucp_values()

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.cucp_helm_chart,
            self.state.oai_cucp_config_values.model_dump(exclude_none=True, by_alias=True)
        )

    def update_cucp_values(self):
        self.state.oai_cucp_config_values.config.mcc = self.state.current_config.mcc
        self.state.oai_cucp_config_values.config.mnc = self.state.current_config.mnc
        self.state.oai_cucp_config_values.config.tac = str(self.state.current_config.tac)
        self.state.oai_cucp_config_values.config.snssai_list = self.state.current_config.snssai_list
        self.state.oai_cucp_config_values.config.gnb_id = f'0x{self.state.current_config.gnb_id:0>4x}'
        self.state.oai_cucp_config_values.config.amfhost = self.state.current_config.amf

    def update_cucp(self):
        self.update_cucp_values()
        self.provider.update_values_helm_chart(
            self.state.cucp_helm_chart,
            self.state.oai_cucp_config_values.model_dump(exclude_none=True, by_alias=True)
        )
