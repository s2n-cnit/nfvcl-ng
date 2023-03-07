from typing import Optional, Literal, List
from pydantic import BaseModel, Field, conlist
from .vyos_area_model import VyOSArea
from .vyos_nat_rules_model import VyOSSourceNATRule, VyOSDestNATRule, VyOS1to1NATRule

class VyOSBlueprintCreate(BaseModel):
    """Class used to represent creation model for Vyos blueprint.
    This class is used to list fields used when calling the creation
    API of NFVCL for the Vyos blueprint"""

    type: Literal['VyOSBlue']
    callbackURL: Optional[str] = Field(
        None,
        description='url that will be used to notify when the blueprint processing finishes',
    )
    areas: conlist(VyOSArea, min_items=1) = Field(
        ...,
        description='list of areas (with relative configuration) to instantiate the Blueprint. ',
    )

    class Config:
        use_enum_values = True

class VyOSBlueprintSNATCreate(BaseModel):
    callbackURL: Optional[str] = Field(
        None,
        description='url that will be used to notify when the blueprint processing finishes',
    )
    operation: Literal['snat']
    area : int
    router_name : str
    rules: List[VyOSSourceNATRule]

class VyOSBlueprintDNATCreate(BaseModel):
    callbackURL: Optional[str] = Field(
        None,
        description='url that will be used to notify when the blueprint processing finishes',
    )
    operation: Literal['dnat']
    area : int
    router_name : str
    rules: List[VyOSDestNATRule]

class VyOSBlueprintNAT1to1Create(BaseModel):
    callbackURL: Optional[str] = Field(
        None,
        description='url that will be used to notify when the blueprint processing finishes',
    )
    operation: Literal['1to1nat']
    area : int
    router_name : str
    rules: List[VyOS1to1NATRule]

class VyOSBlueprintNATdelete(BaseModel):
    callbackURL: Optional[str] = Field(
        None,
        description='url that will be used to notify when the blueprint processing finishes',
    )
    operation: Literal['del_nat']
    area : int
    router_name : str
    rules: List[int] = Field(title="List of rules to delete in the specified vyos instance of the blueprint")