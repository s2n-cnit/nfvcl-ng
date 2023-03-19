from pydantic import BaseModel, Field, conlist
from typing import List, Optional
from enum import Enum
from ipaddress import IPv4Network, IPv4Address


class NetworkTypeEnum(str, Enum):
    vlan: str = 'vlan'
    vxlan: str = 'vxlan'
    gre: str = 'gre'
    flat: str = 'flat'


class IPv4pool(BaseModel):
    start: IPv4Address
    end: IPv4Address


class IPv4reservedRange(IPv4pool):
    owner: str


class NetworkModel(BaseModel):
    name: str
    external: bool = False
    type: NetworkTypeEnum
    vid: Optional[int]
    dhcp: bool = True
    cidr: IPv4Network
    gateway_ip: Optional[IPv4Network] = None
    allocation_pool: List[IPv4pool] = []
    reserved_ranges: List[IPv4reservedRange] = []
    dns_nameservers: List[IPv4Address] = []


class RouterModel(BaseModel):
    class RouterPortModel(BaseModel):
        net: str
        ip_addr: IPv4Address

    name: str
    ports: List[RouterPortModel] = []


class PduInterface(BaseModel):
    vld: str
    name: str
    ip_address: IPv4Address = Field(alias='ip-address')
    network_name: str = Field(alias='vim-network-name')
    mgt: bool

    class Config:
        allow_population_by_field_name = True


class PduModel(BaseModel):
    name: str
    area: int
    type: str
    user: str
    passwd: str
    nfvo_onboarded: bool = False
    implementation: str
    config: dict
    interface: conlist(PduInterface, min_items=1)
