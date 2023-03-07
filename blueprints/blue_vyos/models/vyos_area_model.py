from pydantic import BaseModel, Field, conlist
from .vyos_config_model import VyOSConfig

class VyOSArea(BaseModel):
    id: int = Field(default="0",title="The area to deploy all routers described by the config_list")
    config_list: conlist(VyOSConfig, min_items=1) = Field(..., description="list of VyOS instances in the given area")