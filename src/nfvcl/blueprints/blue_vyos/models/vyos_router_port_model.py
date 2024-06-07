from copy import deepcopy
from ipaddress import IPv4Address, IPv4Network
from pydantic import BaseModel, Field, field_serializer, field_validator
from typing import Optional, Dict, Any


class VyOSRouterPortModel(BaseModel):
    net_name: str = Field(default="network1",
                          title="The name of the network that will be attached to the router. This"
                                "name must correspond to the network name of networks in the topology")
    interface_name: Optional[str] = Field(default=None)
    osm_interface_name: Optional[str] = Field(default=None)
    ip_addr: Optional[IPv4Address] = Field(default=None)
    network: Optional[IPv4Network] = Field(default=None)

    @field_serializer('ip_addr')
    def serialize_ip_addr(self, ip_addr: IPv4Address, _info):
        if ip_addr is not None:
            return ip_addr.exploded
        return None

    @field_serializer('network')
    def serialize_dt(self, network: IPv4Network, _info):
        if network is not None:
            return network.exploded
        return None

    @field_validator('ip_addr')
    @classmethod
    def validate_ip_a(cls, ip_a) -> IPv4Address:
        to_ret: IPv4Address
        if isinstance(ip_a, str):
            return IPv4Address(ip_a)
        elif isinstance(ip_a, IPv4Address):
            return ip_a

    @field_validator('network')
    @classmethod
    def validate_net(cls, network) -> IPv4Network:
        to_ret: IPv4Network
        if isinstance(network, str):
            return IPv4Network(network)
        elif isinstance(network, IPv4Network):
            return network