from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class NetEndpoints(BaseModel):
    data: str = Field(..., description='identifier of the topology network where to attach the VO')


class Config(BaseModel):
    network_endpoints: NetEndpoints


class Area(BaseModel):
    id: int = Field(..., description='identifier of the topology area to be used for deployment')


class VoBlueprintRequestInstance(BaseModel):
    type: Literal["vo"] = Field(
        None, description='type of the requested Blueprint'
    )
    callbackURL: Optional[str] = Field(
        None,
        description='url that will be used to notify when the topology terraforming ends',
    )
    config: Config = Field(
        None,
        description='parameters for the day2 configuration of the Blueprint instance',
    )
    areas: Optional[List[Area]] = Field(
        None,
        description='list of Areas to be used for the Blueprint instantiation',
        min_items=1,
    )
