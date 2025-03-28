from abc import abstractmethod
from typing import Optional, TypeVar, Generic

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_cucp import Generic5GCUCPBlueprintNG, Generic5GCUCPBlueprintNGState
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.g5.ran import CUCPBlueCreateModel, RanInterfacesIps


class Generic5GCUCPK8sBlueprintNGState(Generic5GCUCPBlueprintNGState):
    cucp_helm_chart: Optional[HelmChartResource] = Field(default=None)


StateTypeVar5GCUCPK8s = TypeVar("StateTypeVar5GCUCPK8s", bound=Generic5GCUCPK8sBlueprintNGState)
CreateConfigTypeVar5GCUCPK8s = TypeVar("CreateConfigTypeVar5GCUCPK8s")


class Generic5GCUCPK8sBlueprintNG(Generic5GCUCPBlueprintNG[Generic5GCUCPK8sBlueprintNGState, CUCPBlueCreateModel], Generic[StateTypeVar5GCUCPK8s, CreateConfigTypeVar5GCUCPK8s]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GCUCPK8sBlueprintNGState] = StateTypeVar5GCUCPK8s):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GCUCPK8s:
        return super().state

    @abstractmethod
    def create_cucp(self):
        pass

    @abstractmethod
    def update_cucp(self):
        pass

    @abstractmethod
    def get_svc_name(self) -> str:
        pass

    def get_cucp_interfaces_ip(self) -> RanInterfacesIps:
        svc_name = self.get_svc_name()
        interfaces = RanInterfacesIps(
            n2=self.state.oai_cucp_config_values.multus.n2_interface.ip_add if self.state.oai_cucp_config_values.multus.n2_interface.create else self.state.cucp_helm_chart.services[f"{svc_name}"].external_ip[0],
            e1CuCp=self.state.oai_cucp_config_values.multus.e1_interface.ip_add if self.state.oai_cucp_config_values.multus.e1_interface.create else self.state.cucp_helm_chart.services[f"{svc_name}"].external_ip[0],
            f1CuCp=self.state.oai_cucp_config_values.multus.f1c_interface.ip_add if self.state.oai_cucp_config_values.multus.f1c_interface.create else self.state.cucp_helm_chart.services[f"{svc_name}"].external_ip[0],
        )
        return interfaces
