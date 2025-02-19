import copy
from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_cu_k8s import Generic5GCUK8sBlueprintNGState, Generic5GCUK8sBlueprintNG
from nfvcl.blueprints_ng.modules.oai import oai_default_cu_config
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.core5g.OAI_Models import CU
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_models.blueprint_ng.g5.ran import CUBlueCreateModel

OAI_CU_BLUE_TYPE = "oai_cu"


class OAICuBlueprintNGState(Generic5GCUK8sBlueprintNGState):
    oai_cu_config_values: Optional[CU] = Field(default=None)


@blueprint_type(OAI_CU_BLUE_TYPE)
class OpenAirInterfaceCu(Generic5GCUK8sBlueprintNG[OAICuBlueprintNGState, CUBlueCreateModel]):

    def get_svc_name(self) -> str:
        return "oai-cu-lb"

    def __init__(self, blueprint_id: str, state_type: type[Generic5GCUK8sBlueprintNGState] = OAICuBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_cu(self):
        self.logger.info("Starting creation of Open Air Interface CU blueprint")

        self.state.oai_cu_config_values = copy.deepcopy(oai_default_cu_config.default_cu_config)

        # self.state.current_config = create_model
        self.state.cu_helm_chart = HelmChartResource(
            area=self.state.current_config.area_id,
            name="cu",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/oai-cu-2.1.0.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.cu_helm_chart)

        if self.state.current_config.networks.n2.type == NetworkEndPointType.MULTUS:
            net_n2 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.n2.net_name)
            self.state.oai_cu_config_values.multus.n2_interface.set_multus(True, net_n2, self.state.current_config.networks.n2.routes)
            self.state.oai_cu_config_values.config.n2_if_name = "n2"

        if self.state.current_config.networks.n3.type == NetworkEndPointType.MULTUS:
            net_n3 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.n3.net_name)
            self.state.oai_cu_config_values.multus.n3_interface.set_multus(True, net_n3, self.state.current_config.networks.n3.routes)
            self.state.oai_cu_config_values.config.n3_if_name = "n3"

        if self.state.current_config.networks.f1.type == NetworkEndPointType.MULTUS:
            net_f1 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.f1.net_name)
            self.state.oai_cu_config_values.multus.f1_interface.set_multus(True, net_f1, self.state.current_config.networks.f1.routes)
            self.state.oai_cu_config_values.config.f1_if_name = "f1"

        if self.state.oai_cu_config_values.config.f1_if_name != self.state.oai_cu_config_values.config.n3_if_name:
            self.state.oai_cu_config_values.config.f1cu_port = "2152"
            self.state.oai_cu_config_values.config.f1du_port = "2152"

        self.update_cu_values()

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.cu_helm_chart,
            self.state.oai_cu_config_values.model_dump(exclude_none=True, by_alias=True)
        )

    def update_cu_values(self):
        self.state.oai_cu_config_values.config.mcc = self.state.current_config.mcc
        self.state.oai_cu_config_values.config.mnc = self.state.current_config.mnc
        self.state.oai_cu_config_values.config.tac = str(self.state.current_config.tac)
        self.state.oai_cu_config_values.config.snssai_list = self.state.current_config.snssai_list
        self.state.oai_cu_config_values.config.gnb_id = f'0x{self.state.current_config.gnb_id:0>4x}'
        self.state.oai_cu_config_values.config.amfhost = self.state.current_config.amf

    def update_cu(self):
        self.update_cu_values()
        self.provider.update_values_helm_chart(
            self.state.cu_helm_chart,
            self.state.oai_cu_config_values.model_dump(exclude_none=True, by_alias=True)
        )
