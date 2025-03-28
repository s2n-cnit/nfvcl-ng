from abc import abstractmethod
from typing import Optional, TypeVar, Generic

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_cuup import Generic5GCUUPBlueprintNGState, Generic5GCUUPBlueprintNG
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.g5.ran import CUUPBlueCreateModel, RanInterfacesIps


class Generic5GCUUPK8sBlueprintNGState(Generic5GCUUPBlueprintNGState):
    cuup_helm_chart: Optional[HelmChartResource] = Field(default=None)


StateTypeVar5GCUUPK8s = TypeVar("StateTypeVar5GCUUPK8s", bound=Generic5GCUUPK8sBlueprintNGState)
CreateConfigTypeVar5GCUUPK8s = TypeVar("CreateConfigTypeVar5GCUUPK8s")


class Generic5GCUUPK8sBlueprintNG(Generic5GCUUPBlueprintNG[Generic5GCUUPK8sBlueprintNGState, CUUPBlueCreateModel], Generic[StateTypeVar5GCUUPK8s, CreateConfigTypeVar5GCUUPK8s]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GCUUPK8sBlueprintNGState] = StateTypeVar5GCUUPK8s):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GCUUPK8s:
        return super().state

    @abstractmethod
    def create_cuup(self):
        pass

    @abstractmethod
    def update_cuup(self):
        pass

    @abstractmethod
    def get_svc_name(self) -> str:
        pass

    def get_cuup_interfaces_ip(self) -> RanInterfacesIps:
        svc_name = self.get_svc_name()
        interfaces = RanInterfacesIps(
            n3=self.state.oai_cuup_config_values.multus.n3_interface.ip_add if self.state.oai_cuup_config_values.multus.n3_interface.create else self.state.cuup_helm_chart.services[f"{svc_name}"].external_ip[0],
            e1CuUp=self.state.oai_cuup_config_values.multus.e1_interface.ip_add if self.state.oai_cuup_config_values.multus.e1_interface.create else self.state.cuup_helm_chart.services[f"{svc_name}"].external_ip[0],
            f1CuUp=self.state.oai_cuup_config_values.multus.f1u_interface.ip_add if self.state.oai_cuup_config_values.multus.f1u_interface.create else self.state.cuup_helm_chart.services[f"{svc_name}"].external_ip[0],
        )
        return interfaces
