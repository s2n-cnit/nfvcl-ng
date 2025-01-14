from __future__ import annotations

from typing import List

from pydantic import Field

from nfvcl_core.models.blueprints.blueprint import BlueprintNGCreateModel


class VyOSCreateModel(BlueprintNGCreateModel):
    """
    This class represents the model for the creation request
    """
    mgmt_net: str = Field()
    data_nets: List[str] = Field(min_length=1)
    area: int
