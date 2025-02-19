import copy
from abc import abstractmethod
from typing import Optional, TypeVar, Generic, final

from pydantic import Field

from nfvcl_core.blueprints import BlueprintNG
from nfvcl_core_models.blueprints import BlueprintNGState
from nfvcl_models.blueprint_ng.g5.ran import DUBlueCreateModel


class Generic5GDUBlueprintNGState(BlueprintNGState):
    current_config: Optional[DUBlueCreateModel] = Field(default=None)


StateTypeVar5GDU = TypeVar("StateTypeVar5GDU", bound=Generic5GDUBlueprintNGState)
CreateConfigTypeVar5GDU = TypeVar("CreateConfigTypeVar5GDU")


class Generic5GDUBlueprintNG(BlueprintNG[Generic5GDUBlueprintNGState, DUBlueCreateModel], Generic[StateTypeVar5GDU, CreateConfigTypeVar5GDU]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GDUBlueprintNGState] = StateTypeVar5GDU):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GDU:
        return super().state

    @final
    def create(self, create_model: DUBlueCreateModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.create_du()

    @abstractmethod
    def create_du(self):
        pass

    @final
    def update(self, create_model: DUBlueCreateModel):
        self.state.current_config = copy.deepcopy(create_model)
        self.update_du()

    @abstractmethod
    def update_du(self):
        pass

    @abstractmethod
    def get_du_interfaces_ip(self):
        pass
