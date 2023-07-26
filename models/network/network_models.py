import copy
from pydantic import BaseModel, Field, conlist
from typing import List, Optional, Union
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
    gateway_ip: Optional[IPv4Network] = None  # TODO Should it be IPv4 address?
    allocation_pool: List[IPv4pool] = []
    reserved_ranges: List[IPv4reservedRange] = []
    dns_nameservers: List[IPv4Address] = []

    def to_dict(self) -> dict:
        """
        IPv4pool, IPv4reservedRange, IPv4Network ... are NOT json serializable.
        Trying to solve the problem with this function

        Returns:
            a dictionary representation of the NetworkModel object.
        """
        # todo add translation also of IPv4pool, IPv4reservedRange
        to_return = copy.deepcopy(self)
        to_return.cidr = self.cidr.with_prefixlen
        if to_return.gateway_ip is not None:
            to_return.gateway_ip = self.gateway_ip.with_prefixlen

        for i in range(0, len(to_return.dns_nameservers)):
            to_return.dns_nameservers[i] = to_return.dns_nameservers[i].exploded

        for i in range(0, len(to_return.reserved_ranges)):
            res_range_dict: dict = {"owner": to_return.reserved_ranges[i].owner,
                                    "end": to_return.reserved_ranges[i].end.exploded,
                                    "start": to_return.reserved_ranges[i].start.exploded}
            to_return.reserved_ranges[i] = res_range_dict

        for i in range(0, len(to_return.allocation_pool)):
            range_dict: dict = {"end": to_return.allocation_pool[i].end.exploded,
                                "start": to_return.allocation_pool[i].start.exploded}
            to_return.allocation_pool[i] = range_dict

        return to_return.dict()


class RouterModel(BaseModel):
    class RouterPortModel(BaseModel):
        net: str
        ip_addr: IPv4Address

    name: str
    ports: List[RouterPortModel] = []


class PduInterface(BaseModel):
    vld: str
    name: str
    ip_address: Union[str,IPv4Address] = Field(alias='ip-address')
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
