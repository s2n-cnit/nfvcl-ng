import copy
from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_cuup_k8s import Generic5GCUUPK8sBlueprintNGState, Generic5GCUUPK8sBlueprintNG
from nfvcl.blueprints_ng.modules.oai import oai_default_cu_up_config
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.core5g.OAI_Models import CUUP
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_models.blueprint_ng.g5.ran import CUUPBlueCreateModel

OAI_CUUP_BLUE_TYPE = "oai_cu-up"


class OAICuupBlueprintNGState(Generic5GCUUPK8sBlueprintNGState):
    oai_cuup_config_values: Optional[CUUP] = Field(default=None)


@blueprint_type(OAI_CUUP_BLUE_TYPE)
class OpenAirInterfaceCuup(Generic5GCUUPK8sBlueprintNG[OAICuupBlueprintNGState, CUUPBlueCreateModel]):

    def get_svc_name(self) -> str:
        return "oai-cu-up-lb"

    def __init__(self, blueprint_id: str, state_type: type[Generic5GCUUPK8sBlueprintNGState] = OAICuupBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_cuup(self):
        self.logger.info("Starting creation of Open Air Interface CUUP blueprint")

        self.state.oai_cuup_config_values = copy.deepcopy(oai_default_cu_up_config.default_cuup_config)

        # self.state.current_config = create_model
        self.state.cuup_helm_chart = HelmChartResource(
            area=self.state.current_config.area_id,
            name="cuup",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/oai-cu-up-2.1.0.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.cuup_helm_chart)

        if self.state.current_config.networks.n3.type == NetworkEndPointType.MULTUS:
            net_n3 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.n3.net_name)
            self.state.oai_cuup_config_values.multus.n3_interface.set_multus(True, net_n3, self.state.current_config.networks.n3.routes)
            self.state.oai_cuup_config_values.config.n3_if_name = "n3"

        if self.state.current_config.networks.e1.type == NetworkEndPointType.MULTUS:
            net_e1 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.e1.net_name)
            self.state.oai_cuup_config_values.multus.e1_interface.set_multus(True, net_e1, self.state.current_config.networks.e1.routes)
            self.state.oai_cuup_config_values.config.e1_if_name = "e1"

        if self.state.current_config.networks.f1.type == NetworkEndPointType.MULTUS:
            net_f1 = self.provider.reserve_k8s_multus_ip(self.state.current_config.area_id, self.state.current_config.networks.f1.net_name)
            self.state.oai_cuup_config_values.multus.f1u_interface.set_multus(True, net_f1, self.state.current_config.networks.f1.routes)
            self.state.oai_cuup_config_values.config.f1_if_name = "f1u"

        if self.state.oai_cuup_config_values.config.f1_if_name != self.state.oai_cuup_config_values.config.n3_if_name:
            self.state.oai_cuup_config_values.config.f1cu_port = "2152"
            self.state.oai_cuup_config_values.config.f1du_port = "2152"



        self.update_cuup_values()

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.cuup_helm_chart,
            self.state.oai_cuup_config_values.model_dump(exclude_none=True, by_alias=True)
        )

    def update_cuup_values(self):
        self.state.oai_cuup_config_values.config.mcc = self.state.current_config.mcc
        self.state.oai_cuup_config_values.config.mnc = self.state.current_config.mnc
        self.state.oai_cuup_config_values.config.tac = str(self.state.current_config.tac)
        self.state.oai_cuup_config_values.config.snssai_list = self.state.current_config.snssai_list
        self.state.oai_cuup_config_values.config.cu_cp_host = self.state.current_config.cucp_host
        self.state.oai_cuup_config_values.config.gnb_id = f'0x{self.state.current_config.gnb_id:0>4x}'

        routes_list = []
        for route in self.state.current_config.additional_routes:
            tmp = route.as_linux_replace_command()
            if tmp not in routes_list:
                routes_list.append(tmp)
        self.state.oai_cuup_config_values.config.additional_routes = routes_list

    def update_cuup(self):
        self.update_cuup_values()
        self.provider.update_values_helm_chart(
            self.state.cuup_helm_chart,
            self.state.oai_cuup_config_values.model_dump(exclude_none=True, by_alias=True)
        )

    def restart_cuup(self):
        self.logger.info("Restarting CUUP")
        self.provider.restart_all_deployments(self.state.cuup_helm_chart, self.id)
