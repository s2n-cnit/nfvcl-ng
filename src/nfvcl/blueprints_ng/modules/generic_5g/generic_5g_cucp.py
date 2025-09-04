import copy
from abc import abstractmethod
from typing import Optional, TypeVar, Generic, final

from pydantic import Field

from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core_models.blueprints.blueprint import BlueprintNGState
from nfvcl_models.blueprint_ng.g5.ran import CUCPBlueCreateModel


class Generic5GCUCPBlueprintNGState(BlueprintNGState):
    current_config: Optional[CUCPBlueCreateModel] = Field(default=None)


StateTypeVar5GCUCP = TypeVar("StateTypeVar5GCUCP", bound=Generic5GCUCPBlueprintNGState)
CreateConfigTypeVar5GCUCP = TypeVar("CreateConfigTypeVar5GCUCP")


class Generic5GCUCPBlueprintNG(BlueprintNG[Generic5GCUCPBlueprintNGState, CUCPBlueCreateModel], Generic[StateTypeVar5GCUCP, CreateConfigTypeVar5GCUCP]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GCUCPBlueprintNGState] = StateTypeVar5GCUCP):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GCUCP:
        return super().state

    @final
    def create(self, create_model: CUCPBlueCreateModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.create_cucp()

    @abstractmethod
    def create_cucp(self):
        pass

    @final
    def update(self, create_model: CUCPBlueCreateModel):
        self.state.current_config = copy.deepcopy(create_model)
        self.update_cucp()

    @abstractmethod
    def update_cucp(self):
        pass

    @abstractmethod
    def restart_cucp(self):
        pass

    @abstractmethod
    def get_cucp_interfaces_ip(self):
        pass
