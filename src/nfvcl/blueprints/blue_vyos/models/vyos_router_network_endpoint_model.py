from typing import List
from pydantic import BaseModel, Field
from nfvcl.blueprints.blue_vyos.models.vyos_router_port_model import VyOSRouterPortModel

class VyOSRouterNetworkEndpoints(BaseModel):
    mgt: VyOSRouterPortModel = Field(..., description='name of the topology network to be used for management')
    data_nets: List[VyOSRouterPortModel] = Field(..., description='topology networks attached to VyOS router')
