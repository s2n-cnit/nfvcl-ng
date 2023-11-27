from typing import Literal

from blueprints.blue_5g_base.models import Create5gModel


class BlueSDCoreCreateModel(Create5gModel):
    type: Literal["BlueSDCore"]
