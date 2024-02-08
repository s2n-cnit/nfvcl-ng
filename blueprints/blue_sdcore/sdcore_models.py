from typing import Literal, Optional, List

from pydantic import Field, constr

from blueprints.blue_5g_base.models import Create5gModel
from blueprints.blue_5g_base.models.blue_5g_model import SubSubscribers, SubSliceProfiles, SubArea, SubAreaOnlyId
from models.base_model import NFVCLBaseModel


class BlueSDCoreCreateModel(Create5gModel):
    type: Literal["BlueSDCore"]


class BlueSDCoreAddSubscriberModel(SubSubscribers):
    type: Literal["BlueSDCore"] = Field(default="BlueSDCore")
    operation: Literal["add_ues"] = Field(default="add_ues")


class BlueSDCoreDelSubscriberModel(NFVCLBaseModel):
    type: Literal["BlueSDCore"] = Field(default="BlueSDCore")
    operation: Literal["del_ues"] = Field(default="del_ues")
    imsi: str = Field()


class BlueSDCoreAddSliceModel(SubSliceProfiles):
    type: Literal["BlueSDCore"] = Field(default="BlueSDCore")
    operation: Literal["add_slice"] = Field(default="add_slice")
    area_id: int = Field()


class BlueSDCoreDelSliceModel(NFVCLBaseModel):
    type: Literal["BlueSDCore"] = Field(default="BlueSDCore")
    operation: Literal["del_slice"] = Field(default="del_slice")
    sliceId: str = Field()


class BlueSDCoreAddTacModel(SubArea):
    type: Literal["BlueSDCore"] = Field(default="BlueSDCore")
    operation: Literal["add_tac"] = Field(default="add_tac")


class BlueSDCoreDelTacModel(SubArea):
    type: Literal["BlueSDCore"] = Field(default="BlueSDCore")
    operation: Literal["del_tac"] = Field(default="del_tac")
