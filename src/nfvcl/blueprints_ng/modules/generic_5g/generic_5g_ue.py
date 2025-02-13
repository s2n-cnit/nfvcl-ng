import copy
from abc import abstractmethod
from typing import Optional, TypeVar, Generic, final

from pydantic import Field

from nfvcl.models.blueprint_ng.g5.ue import UEBlueCreateModelGeneric
from nfvcl_core.blueprints import BlueprintNG
from nfvcl_core.models.blueprints import BlueprintNGState


class Generic5GUEBlueprintNGState(BlueprintNGState):
    current_config: Optional[UEBlueCreateModelGeneric] = Field(default=None)


StateTypeVar5GUE = TypeVar("StateTypeVar5GUE", bound=Generic5GUEBlueprintNGState)
CreateConfigTypeVar5GUE = TypeVar("CreateConfigTypeVar5GUE")


class Generic5GUEBlueprintNG(BlueprintNG[Generic5GUEBlueprintNGState, UEBlueCreateModelGeneric], Generic[StateTypeVar5GUE, CreateConfigTypeVar5GUE]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GUEBlueprintNGState] = StateTypeVar5GUE):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GUE:
        return super().state

    @final
    def create(self, create_model: UEBlueCreateModelGeneric):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.create_ue()

    @abstractmethod
    def create_ue(self):
        pass

    @final
    def update(self, create_model: UEBlueCreateModelGeneric):
        self.state.current_config = copy.deepcopy(create_model)
        self.update_ue()

    @abstractmethod
    def update_ue(self):
        pass
