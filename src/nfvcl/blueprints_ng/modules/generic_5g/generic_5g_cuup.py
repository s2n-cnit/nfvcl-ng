import copy
from abc import abstractmethod
from typing import Optional, TypeVar, Generic, final

from pydantic import Field

from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core_models.blueprints.blueprint import BlueprintNGState
from nfvcl_models.blueprint_ng.g5.ran import CUUPBlueCreateModel


class Generic5GCUUPBlueprintNGState(BlueprintNGState):
    current_config: Optional[CUUPBlueCreateModel] = Field(default=None)


StateTypeVar5GCUUP = TypeVar("StateTypeVar5GCUUP", bound=Generic5GCUUPBlueprintNGState)
CreateConfigTypeVar5GCUUP = TypeVar("CreateConfigTypeVar5GCUUP")


class Generic5GCUUPBlueprintNG(BlueprintNG[Generic5GCUUPBlueprintNGState, CUUPBlueCreateModel], Generic[StateTypeVar5GCUUP, CreateConfigTypeVar5GCUUP]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GCUUPBlueprintNGState] = StateTypeVar5GCUUP):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GCUUP:
        return super().state

    @final
    def create(self, create_model: CUUPBlueCreateModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.create_cuup()

    @abstractmethod
    def create_cuup(self):
        pass

    @final
    def update(self, create_model: CUUPBlueCreateModel):
        self.state.current_config = copy.deepcopy(create_model)
        self.update_cuup()

    @abstractmethod
    def update_cuup(self):
        pass

    @abstractmethod
    def restart_cuup(self):
        pass

    @abstractmethod
    def get_cuup_interfaces_ip(self):
        pass
