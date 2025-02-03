from abc import abstractmethod
from typing import Generic, TypeVar, Optional, Dict

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import Generic5GUPFBlueprintNGState, Generic5GUPFBlueprintNG
from nfvcl.models.blueprint_ng.g5.upf import UPFBlueCreateModel
from nfvcl_core.models.resources import HelmChartResource


class Generic5GUPFK8SBlueprintNGState(Generic5GUPFBlueprintNGState):
    helm_chart_resources: Dict[str, HelmChartResource] = Field(default_factory=dict)


StateTypeVar5GUPFK8S = TypeVar("StateTypeVar5GUPFK8S", bound=Generic5GUPFK8SBlueprintNGState)
CreateConfigTypeVar5GUPFK8S = TypeVar("CreateConfigTypeVar5GUPFK8S")


class Generic5GUPFK8SBlueprintNG(Generic5GUPFBlueprintNG[Generic5GUPFK8SBlueprintNGState, UPFBlueCreateModel], Generic[StateTypeVar5GUPFK8S, CreateConfigTypeVar5GUPFK8S]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFK8SBlueprintNGState] = StateTypeVar5GUPFK8S):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GUPFK8S:
        return super().state

    @abstractmethod
    def create_upf(self):
        pass

    @abstractmethod
    def update_upf(self):
        pass
