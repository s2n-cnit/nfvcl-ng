from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Cni(Enum):
    flannel = 'flannel'
    calico = 'calico'


class LbType(Enum):
    layer2 = 'layer2'
    layer3 = 'layer3'


class LBPool(BaseModel):
    mode: LbType = Field(
        'layer2', description='Operating mode of Metal-LB. Default Layer-2.'
    )
    net_name: str = Field(
        ..., description='name of the network in the topology'
    )
    ip_start: Optional[str] = Field(default=None)
    ip_end: Optional[str] = Field(default=None)
    range_length: Optional[int] = Field(None,description='Number of IPv4 addresses to reserved if no ip start'
                                                         ' and end are passed. Default 10 addresses.')

    class Config:
        use_enum_values = True