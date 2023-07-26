from pydantic import BaseModel, Field
from ipaddress import IPv4Address, IPv4Network
from typing import Optional

class VyOSRouterPortModel(BaseModel):
    net_name: str = Field(default="network1",
                          title="The name of the network that will be attached to the router. This"
                                "name must correspond to the network name of networks in the topology")
    interface_name: Optional[str]
    osm_interface_name: Optional[str]
    ip_addr: IPv4Address = Field(default=None)
    network: IPv4Network = Field(default=None)
