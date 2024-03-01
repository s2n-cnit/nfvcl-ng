from __future__ import annotations

from typing import List

from pydantic import Field

from blueprints_ng.blueprint_ng import BlueprintNGCreateModel


class VyOSCreateModel(BlueprintNGCreateModel):
    """
    This class represent the model for the create request
    """
    mgmt_net: str = Field()
    data_nets: List[str] = Field(min_items=1)
    area: int
