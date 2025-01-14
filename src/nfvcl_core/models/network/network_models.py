from enum import Enum
from ipaddress import IPv4Network, IPv4Address
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator, field_serializer

from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.network.ipam_models import SerializableIPv4Address, SerializableIPv4Network


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
            raise ValueError("IPv4Pool validator: The type of >start< field is not recognized ->> {}".format(val))

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
            raise ValueError("IPv4Pool validator: The type of >end< field is not recognized ->> {}".format(val))

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
    vid: Optional[int] = Field(default=None)
    dhcp: bool = True
    ids: List[dict] = Field(default=[])
    cidr: IPv4Network
    gateway_ip: Optional[IPv4Address] = Field(default=None)
    allocation_pool: List[IPv4Pool] = Field(default=[], description='The list of ranges that are used by the VIM to assign IP addresses to VMs (Reserved to VIM)')
    reserved_ranges: List[IPv4ReservedRange] = Field(default=[], description='The list of ranges that have been reserved by deployed blueprints')
    dns_nameservers: List[IPv4Address] = Field(default=[], description='List of DNS IPs avaiable in this network')

    @classmethod
    def build_network_model(cls, name: str, type: NetworkTypeEnum, cidr: IPv4Network):
        return NetworkModel(name=name, type=type, cidr=cidr)

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, NetworkModel):
            return self.name == other.name
        return False

    @field_validator('gateway_ip')
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


# TODO remove as soon as OSM is removed
class PduInterface(BaseModel):
    vld: str
    name: str
    mgt: bool = Field(alias='mgmt')
    intf_type: Optional[str] = Field(default=None)
    ip_address: Union[str, IPv4Address] = Field(alias='ip-address')  # TODO pass to only str???
    network_name: str = Field(alias='vim-network-name')
    port_security_enabled: bool = Field(default=True, alias="port-security-enabled")

    @classmethod
    def build_pdu(cls, vld: str, name: str, mgt: bool, ip_address: str, network_name: str):
        return PduInterface(vld=vld, name=name, mgt=mgt, ip_address=ip_address, network_name=network_name)

    def get_ip(self) -> List[IPv4Address]:
        """
        Return a list of IP of the VLD (Every interface can have multiple IPs
        Returns:
            A list of IP, usually composed only by a single IP, but, when the interface has floating IPs (for example)
            more than one IP is returned.
        """
        return_list = []
        ip_list_str = self.ip_address.split(";")
        for ip in ip_list_str:
            return_list.append(IPv4Address(ip))

        return return_list

    def get_ip_str(self) -> List[str]:
        """
        Return a list of IP of the VLD (Every interface can have multiple IPs
        Returns:
            A list of IP, usually composed only by a single IP, but, when the interface has floating IPs (for example)
            more than one IP is returned.
        """
        ip_list_str = self.ip_address.split(";")

        return ip_list_str

    class Config:
        populate_by_name = True


class NetworkInterfaceModel(NFVCLBaseModel):
    """
    Represents a network interface
    """
    name: str = Field(description="The name of the network interface to be used inside NFVCL to find the correct interface")
    mgmt: bool = Field(default=False, description="True if this interface is the management one, there shouldn't be more than one")
    interface_name: Optional[str] = Field(default=None, description="The name of the network interface like ens18")
    ip: SerializableIPv4Address = Field(description="The IP(v4 or v6) address of the network interface")
    network: Optional[SerializableIPv4Network] = Field(default=None, description="The network attached to the network interface")
    gateway: Optional[SerializableIPv4Address] = Field(default=None, description="The IPv4 address of the gateway on the network attached")


class PduType(str, Enum):
    LINUX: str = 'LINUX'
    GNB: str = 'GNB'
    LWGATEWAY: str = 'LWGATEWAY'
    RU: str = 'RU'
    CUDU: str = 'CUDU'
    CORE5G: str = 'CORE5G'

class PduModel(BaseModel):
    """
    Model for a Physical deployment unit (PDU) -> RU, gNB...
    """
    name: str = Field(description="The name and identifier of the PDU")
    area: int = Field(description="The area where the PDU is located")
    type: PduType = Field(description="The type of PDU. E.g. gnb, RU, Lorawan gateway...")
    instance_type: str = Field(description="The specific type of PDU like UERANSIM for gnb, used to find the class to configure the PDU")
    description: Optional[str] = Field(default=None, description="A description of the PDU")

    network_interfaces: List[NetworkInterfaceModel] = Field(default=[], description="Network interfaces actives on the PDU")
    username: Optional[str] = Field(default=None, description="The username for accessing the PDU")
    password: Optional[str] = Field(default=None, description="The password of the management user")
    become_password: Optional[str] = Field(default=None, description="Password for privilege escalation if needed")

    config: dict = Field(default={}, description="Additional configuration parameters needed by the PDU to be accessed/configured")

    locked_by: Optional[str] = Field(default=None, description="The id of the blueprint who locked the PDU")
    # last_applied_config: dict = Field(default={}, description="The last configuration used by the configurator to set up the device")

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, PduModel):
            return self.name == other.name
        return False

    def get_mgmt_ip(self) -> str:
        """
        Get the management ip address for this PDU

        Returns: IP address of the management interface
        """
        for interface in self.network_interfaces:
            if interface.mgmt:
                return interface.ip.exploded
