from typing import Optional, Literal, List

from pydantic import Field

from blueprints_ng.blueprint_ng import BlueprintNGCreateModel
from models.base_model import NFVCLBaseModel


class BlueCreateModelNetworks(NFVCLBaseModel):
    mgt: str = Field()
    n4: str = Field()
    n3: str = Field()
    n6: str = Field()


class UPFBlueCreateModel(BlueprintNGCreateModel):
    area_id: int = Field()
    networks: BlueCreateModelNetworks = Field()

#####################################################
class DnnModel(NFVCLBaseModel):
    name: Optional[str] = Field(default=None)
    cidr: Optional[str] = Field(default=None)


class SliceModel(NFVCLBaseModel):
    id: Optional[str] = Field(default=None)
    type: Literal["EMBB", "URLLC", "MMTC"] = Field(default="EMBB")
    dnnList: Optional[List[DnnModel]] = Field(default=None)


class UpfPayloadModel(NFVCLBaseModel):
    slices: Optional[List[SliceModel]] = Field(default=None)
    nrf_ip: Optional[str] = Field(default=None)
