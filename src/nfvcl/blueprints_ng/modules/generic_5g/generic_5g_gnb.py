import copy
from abc import abstractmethod
from typing import Optional, TypeVar, Generic, final

from pydantic import Field

from nfvcl_models.blueprint_ng.g5.ran import GNBBlueCreateModel
from nfvcl_core.blueprints import BlueprintNG
from nfvcl_core_models.blueprints import BlueprintNGState


class Generic5GGNBBlueprintNGState(BlueprintNGState):
    current_config: Optional[GNBBlueCreateModel] = Field(default=None)


StateTypeVar5GGNB = TypeVar("StateTypeVar5GGNB", bound=Generic5GGNBBlueprintNGState)
CreateConfigTypeVar5GGNB = TypeVar("CreateConfigTypeVar5GGNB")


class Generic5GGNBBlueprintNG(BlueprintNG[Generic5GGNBBlueprintNGState, GNBBlueCreateModel], Generic[StateTypeVar5GGNB, CreateConfigTypeVar5GGNB]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GGNBBlueprintNGState] = StateTypeVar5GGNB):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GGNB:
        return super().state

    @final
    def create(self, create_model: GNBBlueCreateModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.create_gnb()

    @abstractmethod
    def create_gnb(self):
        pass

    @final
    def update(self, create_model: GNBBlueCreateModel):
        self.state.current_config = copy.deepcopy(create_model)
        self.update_gnb()

    @abstractmethod
    def update_gnb(self):
        pass

    @abstractmethod
    def get_gnb_interfaces_ip(self):
        pass
