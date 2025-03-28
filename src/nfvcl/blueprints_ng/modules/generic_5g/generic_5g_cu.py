import copy
from abc import abstractmethod
from typing import Optional, TypeVar, Generic, final

from pydantic import Field

from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core_models.blueprints.blueprint import BlueprintNGState
from nfvcl_models.blueprint_ng.g5.ran import CUBlueCreateModel


class Generic5GCUBlueprintNGState(BlueprintNGState):
    current_config: Optional[CUBlueCreateModel] = Field(default=None)


StateTypeVar5GCU = TypeVar("StateTypeVar5GCU", bound=Generic5GCUBlueprintNGState)
CreateConfigTypeVar5GCU = TypeVar("CreateConfigTypeVar5GCU")


class Generic5GCUBlueprintNG(BlueprintNG[Generic5GCUBlueprintNGState, CUBlueCreateModel], Generic[StateTypeVar5GCU, CreateConfigTypeVar5GCU]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GCUBlueprintNGState] = StateTypeVar5GCU):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GCU:
        return super().state

    @final
    def create(self, create_model: CUBlueCreateModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.create_cu()

    @abstractmethod
    def create_cu(self):
        pass

    @final
    def update(self, create_model: CUBlueCreateModel):
        self.state.current_config = copy.deepcopy(create_model)
        self.update_cu()

    @abstractmethod
    def update_cu(self):
        pass

    @abstractmethod
    def get_cu_interfaces_ip(self):
        pass
