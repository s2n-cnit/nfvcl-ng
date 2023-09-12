import copy
from pydantic import BaseModel, Field, conlist, validator
from typing import List, Optional, Union
from enum import Enum
from ipaddress import IPv4Network, IPv4Address


class NetworkTypeEnum(str, Enum):
    vlan: str = 'vlan'
    vxlan: str = 'vxlan'
    gre: str = 'gre'
    flat: str = 'flat'


class IPv4Pool(BaseModel):
    start: IPv4Address
    end: IPv4Address

    @validator('start')
    def start_val(cls, val):
        """
        Allow to initialize IPv4 Objects also by passing a string ('10.0.10.0')
        """
        to_ret: IPv4Address
        if isinstance(val, str):
            return IPv4Address(val)
        elif isinstance(val, IPv4Address):
            return val
        else:
            raise ValueError("IPv4Pool validator: The type of >start< field is not recognized ->> {}". format(val))

    @validator('end')
    def end_val(cls, val):
        """
        Allow to initialize IPv4 Objects also by passing a string ('10.0.10.0')
        """
        to_ret: IPv4Address
        if isinstance(val, str):
            return IPv4Address(val)
        elif isinstance(val, IPv4Address):
            return val
        else:
            raise ValueError("IPv4Pool validator: The type of >end< field is not recognized ->> {}". format(val))


    def to_dict(self) -> dict:
        """
        IPv4pool, IPv4reservedRange, IPv4Network ... are NOT json serializable.
        Trying to solve the problem with this function
        Returns:
            a dictionary representation of the NetworkModel object.
        """
        to_return = copy.deepcopy(self)
        to_return.start = self.start.exploded
        to_return.end = self.end.exploded
        return to_return.dict()


class IPv4ReservedRange(IPv4Pool):
    """
    Extension of IPv4Pool
    """
    owner: str


class NetworkModel(BaseModel):
    name: str
    external: bool = Field(default=False)
    type: NetworkTypeEnum
    vid: Optional[int]
    dhcp: bool = True
    ids: List[dict] = Field(default=[])
    cidr: IPv4Network
    gateway_ip: Optional[IPv4Network] = None  # TODO Should it be IPv4 address?
    allocation_pool: List[IPv4Pool] = []
    reserved_ranges: List[IPv4ReservedRange] = []
    dns_nameservers: List[IPv4Address] = []

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, NetworkModel):
            return self.name == other.name
        return False

    def to_dict(self) -> dict:
        """
        IPv4pool, IPv4reservedRange, IPv4Network ... are NOT json serializable.
        Trying to solve the problem with this function

        Returns:
            a dictionary representation of the NetworkModel object.
        """
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

    def add_reserved_range(self, reserved_range: IPv4ReservedRange):
        # TODO check existence of range!!!
        self.reserved_ranges.append(reserved_range)


class RouterPortModel(BaseModel):
    net: str
    ip_addr: IPv4Address


class RouterModel(BaseModel):
    name: str
    ports: List[RouterPortModel] = Field(default=[])
    internal_net: List[RouterPortModel] = Field(default=[])
    external_gateway_info: dict = Field(default=None)

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, RouterModel):
            return self.name == other.name
        return False


class PduInterface(BaseModel):
    vld: str
    name: str
    ip_address: Union[str,IPv4Address] = Field(alias='ip-address')
    network_name: str = Field(alias='vim-network-name')
    mgt: bool

    class Config:
        populate_by_name = True


class PduModel(BaseModel):
    name: str
    area: int
    type: str
    user: str
    passwd: str
    nfvo_onboarded: bool = False
    implementation: str
    config: dict
    details: str = Field(default="")
    interface: List[PduInterface] = Field(min_items=1)

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, PduModel):
            return self.name == other.name
        return False
