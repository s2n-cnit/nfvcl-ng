from abc import abstractmethod
from typing import Optional, TypeVar, Generic

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_gnb import Generic5GGNBBlueprintNG, Generic5GGNBBlueprintNGState
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.g5.ran import GNBBlueCreateModel, RanInterfacesIps


class Generic5GGNBK8sBlueprintNGState(Generic5GGNBBlueprintNGState):
    gnb_helm_chart: Optional[HelmChartResource] = Field(default=None)


StateTypeVar5GGNBK8s = TypeVar("StateTypeVar5GGNBK8s", bound=Generic5GGNBK8sBlueprintNGState)
CreateConfigTypeVar5GGNBK8s = TypeVar("CreateConfigTypeVar5GGNBK8s")


class Generic5GGNBK8sBlueprintNG(Generic5GGNBBlueprintNG[Generic5GGNBK8sBlueprintNGState, GNBBlueCreateModel], Generic[StateTypeVar5GGNBK8s, CreateConfigTypeVar5GGNBK8s]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GGNBK8sBlueprintNGState] = StateTypeVar5GGNBK8s):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GGNBK8s:
        return super().state

    @abstractmethod
    def create_gnb(self):
        pass

    @abstractmethod
    def update_gnb(self):
        pass

    @abstractmethod
    def get_svc_name(self) -> str:
        pass

    def get_gnb_interfaces_ip(self) -> RanInterfacesIps:
        svc_name = self.get_svc_name()
        interfaces = RanInterfacesIps(
            n2=self.state.oai_gnb_config_values.multus.n2_interface.ip_add if self.state.oai_gnb_config_values.multus.n2_interface.create else self.state.gnb_helm_chart.services[f"{svc_name}"].external_ip[0],
            n3=self.state.oai_gnb_config_values.multus.n3_interface.ip_add if self.state.oai_gnb_config_values.multus.n3_interface.create else self.state.gnb_helm_chart.services[f"{svc_name}"].external_ip[0],
            ru1=self.state.oai_gnb_config_values.multus.ru1_interface.ip_add if self.state.oai_gnb_config_values.multus.ru1_interface.create else self.state.gnb_helm_chart.services[f"{svc_name}"].external_ip[0],
            ru2=self.state.oai_gnb_config_values.multus.ru2_interface.ip_add if self.state.oai_gnb_config_values.multus.ru2_interface.create else self.state.gnb_helm_chart.services[f"{svc_name}"].external_ip[0]
        )
        return interfaces
