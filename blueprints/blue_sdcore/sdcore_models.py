from typing import Literal, Optional

from pydantic import Field, constr

from blueprints.blue_5g_base.models import Create5gModel
from blueprints.blue_5g_base.models.blue_5g_model import SubSubscribers
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
