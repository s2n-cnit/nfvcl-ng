from abc import abstractmethod
from typing import Optional, TypeVar, Generic

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_du import Generic5GDUBlueprintNG, Generic5GDUBlueprintNGState
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.g5.ran import DUBlueCreateModel, RanInterfacesIps


class Generic5GDUK8sBlueprintNGState(Generic5GDUBlueprintNGState):
    du_helm_chart: Optional[HelmChartResource] = Field(default=None)


StateTypeVar5GDUK8s = TypeVar("StateTypeVar5GDUK8s", bound=Generic5GDUK8sBlueprintNGState)
CreateConfigTypeVar5GDUK8s = TypeVar("CreateConfigTypeVar5GDUK8s")


class Generic5GDUK8sBlueprintNG(Generic5GDUBlueprintNG[Generic5GDUK8sBlueprintNGState, DUBlueCreateModel], Generic[StateTypeVar5GDUK8s, CreateConfigTypeVar5GDUK8s]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GDUK8sBlueprintNGState] = StateTypeVar5GDUK8s):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GDUK8s:
        return super().state

    @abstractmethod
    def create_du(self):
        pass

    @abstractmethod
    def update_du(self):
        pass

    @abstractmethod
    def get_svc_name(self) -> str:
        pass

    def get_du_interfaces_ip(self) -> RanInterfacesIps:
        svc_name = self.get_svc_name()
        interfaces = RanInterfacesIps(
            f1Du=self.state.oai_du_config_values.multus.f1_interface.ip_add if self.state.oai_du_config_values.multus.f1_interface.create else self.state.du_helm_chart.services[f"{svc_name}"].external_ip[0],
            ru1=self.state.oai_du_config_values.multus.ru1_interface.ip_add if self.state.oai_du_config_values.multus.ru1_interface.create else self.state.du_helm_chart.services[f"{svc_name}"].external_ip[0],
            ru2=self.state.oai_du_config_values.multus.ru2_interface.ip_add if self.state.oai_du_config_values.multus.ru2_interface.create else self.state.du_helm_chart.services[f"{svc_name}"].external_ip[0],
        )
        return interfaces
