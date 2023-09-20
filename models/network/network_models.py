from pydantic import BaseModel, Field, field_validator, field_serializer
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

    @field_validator('start')
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

    @field_validator('end')
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

    @field_serializer('start')
    def serialize_start(self, start: IPv4Address, _info):
        if start is not None:
            return start.exploded
        return None

    @field_serializer('end')
    def serialize_end(self, end: IPv4Address, _info):
        if end is not None:
            return end.exploded
        return None


class IPv4ReservedRange(IPv4Pool):
    """
    Extension of IPv4Pool
    """
    owner: str

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        TWO RESERVED RANGE ARE CONSIDERED EQUAL IF SOME OF THE IPs ARE OVERLAPPED.
        """
        if isinstance(other, IPv4ReservedRange):
            if other.start <= self.start <= other.end or other.start <= self.end <= other.end:
                return True
        return False


class NetworkModel(BaseModel):
    name: str
    external: bool = Field(default=False)
    type: NetworkTypeEnum
    vid: Optional[int]
    dhcp: bool = True
    ids: List[dict] = Field(default=[])
    cidr: IPv4Network
    gateway_ip: Optional[IPv4Address] = None
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

    @field_validator('gateway_ip')
    @classmethod
    def end_validator(cls, val):
        """
        Allow to initialize IPv4 Objects also by passing a string ('10.0.10.0')
        """
        if isinstance(val, str):
            return IPv4Address(val)
        elif isinstance(val, IPv4Address):
            return val

    @field_serializer('cidr')
    def serialize_cidr(self, cidr: IPv4Network, _info):
        if cidr is not None:
            return cidr.exploded
        return None

    @field_serializer('gateway_ip')
    def serialize_start(self, gateway_ip: IPv4Address, _info):
        if gateway_ip is not None:
            return gateway_ip.exploded
        return None

    @field_serializer('dns_nameservers')
    def serialize_dns(self, dns_nameservers: List[IPv4Address], _info):
        to_ret: List[str] = []
        for i in range(0, len(dns_nameservers)):
            to_ret.append(dns_nameservers[i].exploded)
        return to_ret

    def add_reserved_range(self, reserved_range: IPv4ReservedRange):
        """
        Add a reserved range to the network
        Args:
            reserved_range: The range to be reserved

        Returns:

        """
        if reserved_range in self.reserved_ranges:
            msg_err = ("Reserved range >{}< is already present in the topology. Or have overlapped IPs with an existing"
                       "range. See IPv4ReservedRange for more info.").format(reserved_range.model_dump())
            raise ValueError(msg_err)
        self.reserved_ranges.append(reserved_range)

    def release_range(self, owner: str, ip_range: IPv4ReservedRange) \
            -> Union[IPv4ReservedRange, None]:
        """
        Release a reserved range in a network Model. The removed reservation is the FIRST that match the owner.
        If a range is given, then the removed IP range will be the desired one.
        !!! Ranges are considered equal if the IPs are overlapping.
        Args:
            owner: The owner of the reservation
            ip_range: The [OPTIONAL] IP range to be removed

        Returns:
            The released range.
        """
        # Looking for the reservation to be removed in every reserved range.
        for reserved_range in self.reserved_ranges:
            if ip_range is None:
                # Checking reserved range has the required owner
                if reserved_range.owner == owner:
                    self.reserved_ranges.remove(reserved_range)
                    return reserved_range
            else:
                # Ensure that the owner inside the reservation is the required one
                assert owner == ip_range.owner
                # Checking reserved range is equal to the required one (owner, start ip, end ip)
                if reserved_range == ip_range:
                    self.reserved_ranges.remove(reserved_range)
                    return reserved_range

        return None

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
