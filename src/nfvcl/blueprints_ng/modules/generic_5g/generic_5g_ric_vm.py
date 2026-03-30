from abc import abstractmethod
from typing import Dict, TypeVar, Generic

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_ric import Generic5GRICBlueprintNGState, Generic5GRICBlueprintNG
from nfvcl_core_models.resources import VmResource
from nfvcl_models.blueprint_ng.g5.ric import RICBlueCreateModel, RICRunXappModel, RICOnboardXappModel, RicDeleteXappModel


class Generic5GRICVMBlueprintNGState(Generic5GRICBlueprintNGState):
    vm_resources: Dict[str, VmResource] = Field(default_factory=dict)


StateTypeVar5GRICVM = TypeVar("StateTypeVar5GRICVM", bound=Generic5GRICVMBlueprintNGState)
CreateConfigTypeVar5GRICVM = TypeVar("CreateConfigTypeVar5GRICVM")


class Generic5GRICVMBlueprintNG(Generic5GRICBlueprintNG[Generic5GRICVMBlueprintNGState, RICBlueCreateModel], Generic[StateTypeVar5GRICVM, CreateConfigTypeVar5GRICVM]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GRICVMBlueprintNGState] = StateTypeVar5GRICVM):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GRICVM:
        return super().state

    @abstractmethod
    def create_ric(self):
        pass

    @abstractmethod
    def update_ric(self):
        pass

    @abstractmethod
    def onboard_xapp_ric(self, xapp_data: RICOnboardXappModel):
        pass

    @abstractmethod
    def run_xapp_ric(self, xapp: RICRunXappModel):
        pass

    @abstractmethod
    def get_xapps_ric(self):
        pass

    @abstractmethod
    def delete_xapp_ric(self, xapp: RicDeleteXappModel):
        pass

    @abstractmethod
    def wait_gnb_connection_ric(self):
        pass
