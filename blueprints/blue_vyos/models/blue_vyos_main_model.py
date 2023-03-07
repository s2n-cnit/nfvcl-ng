from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field, conlist
from .vyos_area_model import VyOSArea

class VyOSBlueprint(BaseModel):
    """
    This model represent a vyos blueprint instance. It is used to save and restore the instance state from the DB.
    """
    type: Literal['VyOSBlue']
    callbackURL: Optional[str] = Field(
        None,
        description='url that will be used to notify when the blueprint processing finishes',
    )
    areas: conlist(VyOSArea, min_items=1) = Field(
        ...,
        description='list of areas (with relative configuration) to instantiate the Blueprint. ',
    )

    blueprint_instance_id : str
    blueprint_type: str