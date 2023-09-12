from typing import List

from pydantic import BaseModel, Field, conlist
from .vyos_config_model import VyOSConfig

class VyOSArea(BaseModel):
    id: int = Field(default="0",title="The area to deploy all routers described by the config_list")
    config_list: List[VyOSConfig] = Field(..., description="list of VyOS instances in the given area", min_items=1)