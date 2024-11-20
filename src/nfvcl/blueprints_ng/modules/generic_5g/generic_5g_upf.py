import copy
from abc import abstractmethod
from typing import Generic, TypeVar, Optional, final, List, Dict

from pydantic import Field

from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import day2_function
from nfvcl.blueprints_ng.resources import VmResource
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo, SliceModel
from nfvcl.models.http_models import HttpRequestType


class DeployedUPFInfo(NFVCLBaseModel):
    area: int = Field()
    served_slices: List[SliceModel] = Field(default_factory=list)
    network_info: Optional[UPFNetworkInfo] = Field(default=None)
    vm_resource_id: Optional[str] = Field(default=None)
    vm_configurator_id: Optional[str] = Field(default=None)

    def served_dnns(self) -> List[str]:
        served_dnns_list: List[str] = []
        for served_slice in self.served_slices:
            for served_dnn in served_slice.dnn_list:
                served_dnns_list.append(served_dnn.name)
        return served_dnns_list


class Generic5GUPFBlueprintNGState(BlueprintNGState):
    current_config: Optional[UPFBlueCreateModel] = Field(default=None)
    upf_list: List[DeployedUPFInfo] = Field(default_factory=list)
    vm_resources: Dict[str, VmResource] = Field(default_factory=dict)


StateTypeVar5GUPF = TypeVar("StateTypeVar5GUPF", bound=Generic5GUPFBlueprintNGState)
CreateConfigTypeVar5GUPF = TypeVar("CreateConfigTypeVar5GUPF")


class Generic5GUPFBlueprintNG(BlueprintNG[Generic5GUPFBlueprintNGState, UPFBlueCreateModel], Generic[StateTypeVar5GUPF, CreateConfigTypeVar5GUPF]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFBlueprintNGState] = StateTypeVar5GUPF):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GUPF:
        return super().state

    @final
    def create(self, create_model: UPFBlueCreateModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.create_upf()

    @abstractmethod
    def create_upf(self):
        pass

    @final
    def update(self, create_model: UPFBlueCreateModel):
        self.state.current_config = copy.deepcopy(create_model)
        self.update_upf()

    @abstractmethod
    def update_upf(self):
        pass

    @day2_function("/update", [HttpRequestType.PUT])
    def day2_update_upf(self, update_model: UPFBlueCreateModel):
        """
        Update the UPF configuration, note that with some UPF types this may cause additional VMs to be created
        Args:
            update_model: Same model as the create
        """
        if update_model.area_id != self.state.current_config.area_id:
            raise ValueError("Cannot change the area")
        self.update(update_model)

    def get_upfs_info(self) -> List[DeployedUPFInfo]:
        """
        Get information about the UPF(s) deployed by this blueprint
        Returns: List of DeployedUPFInfo
        """
        return copy.copy(self.state.upf_list)
