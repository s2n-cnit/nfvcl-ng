from typing import List, Any, Optional

from pydantic import Field

from nfvcl_models.blueprint_ng.g5.ue import UESim
from nfvcl_core_models.base_model import NFVCLBaseModel


class UeransimNetworkEndpoints(NFVCLBaseModel):
    mgt: str = Field(..., description='name of the topology network to be used for management')
    n2: str = Field(..., description='name of the topology network to be used by NodeBs to attach the core network')
    n3: str = Field(..., description='name of the topology network to be used by NodeBs to attach the core network')

class UeransimConfig(NFVCLBaseModel):
    network_endpoints: UeransimNetworkEndpoints

class UeransimUe(NFVCLBaseModel):
    id: int = Field(description='UE identifier')
    sims: List[UESim] = Field(description='List of sims in the current UE virtual machine')

    def __eq__(self, other: Any) -> bool:
        """
        Override equals. IF the id is the same, they are the same area
       Args:
            other: the object to be compared

        Returns:
            True if id is the same
        """
        if isinstance(other, UeransimUe):
            if other.id == self.id:
                return True
        return False

class UeransimArea(NFVCLBaseModel):
    id: int = Field(..., description='Area identifier, it will be used as TAC in the NodeB configuration')
    nci: Optional[str] = Field(default=None, description='gNodeB nci identifier')
    idLength: Optional[int] = Field(default=None, description='gNodeB nci identifier length')
    ues: List[UeransimUe] = Field(description='list of virtual UEs to be instantiated')

    def __eq__(self, other: Any) -> bool:
        """
        Override equals. IF the id is the same, they are the same area
        Args:
            other: the object to be compared

        Returns:
            True if id is the same
        """
        if isinstance(other, UeransimArea):
            if other.id == self.id:
                return True
        return False

class UeransimModel(NFVCLBaseModel):
    type: str
    config: UeransimConfig
    areas: List[UeransimArea]
