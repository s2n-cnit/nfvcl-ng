from abc import abstractmethod
from typing import Optional, TypeVar, Generic

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_cu import Generic5GCUBlueprintNGState, Generic5GCUBlueprintNG
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.g5.ran import CUBlueCreateModel, RanInterfacesIps


class Generic5GCUK8sBlueprintNGState(Generic5GCUBlueprintNGState):
    cu_helm_chart: Optional[HelmChartResource] = Field(default=None)


StateTypeVar5GCUK8s = TypeVar("StateTypeVar5GCUK8s", bound=Generic5GCUK8sBlueprintNGState)
CreateConfigTypeVar5GCUK8s = TypeVar("CreateConfigTypeVar5GCUK8s")


class Generic5GCUK8sBlueprintNG(Generic5GCUBlueprintNG[Generic5GCUK8sBlueprintNGState, CUBlueCreateModel], Generic[StateTypeVar5GCUK8s, CreateConfigTypeVar5GCUK8s]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GCUK8sBlueprintNGState] = StateTypeVar5GCUK8s):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GCUK8s:
        return super().state

    @abstractmethod
    def create_cu(self):
        pass

    @abstractmethod
    def update_cu(self):
        pass

    @abstractmethod
    def get_svc_name(self) -> str:
        pass

    def get_cu_interfaces_ip(self) -> RanInterfacesIps:
        svc_name = self.get_svc_name()
        interfaces = RanInterfacesIps(
            n2=self.state.oai_cu_config_values.multus.n2_interface.ip_add if self.state.oai_cu_config_values.multus.n2_interface.create else self.state.cu_helm_chart.services[f"{svc_name}"].external_ip[0],
            n3=self.state.oai_cu_config_values.multus.n3_interface.ip_add if self.state.oai_cu_config_values.multus.n3_interface.create else self.state.cu_helm_chart.services[f"{svc_name}"].external_ip[0],
            f1Cu=self.state.oai_cu_config_values.multus.f1_interface.ip_add if self.state.oai_cu_config_values.multus.f1_interface.create else self.state.cu_helm_chart.services[f"{svc_name}"].external_ip[0],
        )
        return interfaces

