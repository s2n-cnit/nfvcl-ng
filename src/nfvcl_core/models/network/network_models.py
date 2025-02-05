import ipaddress
from enum import Enum
from ipaddress import IPv4Network, IPv4Address
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator

from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.network.ipam_models import SerializableIPv4Address, SerializableIPv4Network
from nfvcl_core.utils.util import generate_id


class NetworkTypeEnum(str, Enum):
    vlan: str = 'vlan'
    vxlan: str = 'vxlan'
    gre: str = 'gre'
    flat: str = 'flat'


class IPv4Pool(NFVCLBaseModel):
    name: str = Field(default_factory=generate_id)
    start: SerializableIPv4Address
    end: SerializableIPv4Address
    used: Optional[List[bool]] = Field(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        if self.used is None:
            self.used = [False] * (int(self.end) - int(self.start) + 1)

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'start' and 'end' attributes)
        """
        if isinstance(other, IPv4Pool):
            if other.start <= self.start <= other.end or other.start <= self.end <= other.end:
                return True
        return False

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

    def range_length(self) -> int:
        return int(self.end) - int(self.start) + 1

    def ip_list(self) -> List[SerializableIPv4Address]:
        """
        Returns a list of all the IPs in the pool
        Returns:
            A list of all the IPs in the pool
        """
        return [self.start + i for i in range(self.range_length())]

    def assign_ip_address(self) -> SerializableIPv4Address | None:
        """
        Assign an IP address to a VM
        Returns:
            The IP address assigned, None if no IP is available
        """
        for i in range(len(self.used)):  # Iterate over the used list and take the first free address
            if not self.used[i]:
                self.used[i] = True
                return self.start + i

        return None

    def release_ip_address(self, ip: SerializableIPv4Address) -> bool:
        """
        Release an IP address from the pool
        Args:
            ip: The IP address to be released

        Returns:
            True if the IP was released, False otherwise
        """
        if self.start <= ip <= self.end and self.used[int(ip) - int(self.start)]:  # Check if the IP is in the range and used
            self.used[int(ip) - int(self.start)] = False
            return True
        return False

    def extend_range_end(self, new_end: SerializableIPv4Address):
        """
        Extend the range of the pool to the end IP
        Args:
            new_end: The end IP of the pool
        """
        if new_end <= self.end:
            raise ValueError("The end IP must be greater than the end IP of the pool")
        self.used.extend([False] * (int(new_end) - int(self.end) + 1))
        self.end = new_end

class PoolAssignation(str, Enum):
    K8S_CLUSTER: str = 'K8S_CLUSTER'
    MANUAL: str = 'MANUAL'


class IPv4ReservedRange(IPv4Pool):
    """
    Extension of IPv4Pool
    """
    owner: str = Field(description="The owner of the reserved range, could be the ID of a kubernetes cluster an ID of a Blueprint....")
    assigned_to: Optional[PoolAssignation] = Field(default=None, description="Type of assignation")

    def __init__(self, **data):
        super().__init__(**data)

    def is_ip_in_range(self, ip: SerializableIPv4Address) -> bool:
        """
        Check if an IP is in the reserved range
        Args:
            ip: The IP to be checked

        Returns:
            True if the IP is in the range, False otherwise
        """
        return self.start <= ip <= self.end

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
    name: str = Field(description="The name of the network")
    external: bool = Field(default=False)  # TODO remove
    type: NetworkTypeEnum  # TODO remove
    vid: Optional[int] = Field(default=None)  # TODO remove
    dhcp: bool = True  # TODO remove
    ids: List[dict] = Field(default=[])  # TODO remove
    cidr: SerializableIPv4Network = Field(description="The CIDR of the network")
    gateway_ip: Optional[SerializableIPv4Address] = Field(default=None, description="The IP of the gateway in this network")
    allocation_pool: List[IPv4Pool] = Field(default=[], description='The pools that can be used to assign IPs. They can be a subset of the CIDR (not all the IPs are available for assignation)')
    reserved_ranges: List[IPv4ReservedRange] = Field(default=[], description='The list of ranges that have been reserved or assigned. They are not available for assignation because they are already in use or they have been manually added there')
    dns_nameservers: List[SerializableIPv4Address] = Field(default=[], description='List of DNS server IPs available in this network')

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

    def add_allocation_pool(self, pool: IPv4Pool):
        """
        Add an allocation pool to the network. This is useful if you want to exclude a range from automatic assignation.
        Args:
            pool: The pool to be added

        Returns:
            The pool added

        Raises: ValueError if the pool is already present in the network
        """
        if pool in self.allocation_pool:
            msg_err = f"Pool >{pool.model_dump(exclude={'used'})}< is already present in the topology. Or have overlapped IPs with an existing pool."
            raise ValueError(msg_err)
        if pool.start in self.cidr and pool.end in self.cidr:
            self.allocation_pool.append(pool)
            return pool
        else:
            msg_err = f"Pool >{pool.model_dump(exclude={'used'})}< is not in the CIDR of the network."
            raise ValueError(msg_err)

    def remove_allocation_pool(self, pool_name: str):
        """
        Remove an allocation pool from the network. This is useful if you want to exclude a range from automatic assignation.
        Args:
            pool_name: The name of the pool to be removed

        Returns:
            The pool removed

        Raises: ValueError if the pool is not present in the network
        """
        for pool in self.allocation_pool:
            if pool.name == pool_name:
                self.allocation_pool.remove(pool)
                return pool
        raise ValueError(f"Pool >{pool_name}< is not present in the topology.")

    @field_validator('gateway_ip')
    def end_validator(cls, val):
        """
        Allow to initialize IPv4 Objects also by passing a string ('10.0.10.0')
        """
        try:
            ipv4_model = SerializableIPv4Address(val)
            return ipv4_model
        except ipaddress.AddressValueError:
            return None

    def add_reserved_range(self, reserved_range: IPv4ReservedRange):
        """
        Add a reserved range to the network. This is useful if you want to exclude a range from automatic assignation.
        Args:
            reserved_range: The range to be reserved

        Returns:
            Reserved range added

        Raises: ValueError if the range is already present in the network
        """
        if reserved_range in self.reserved_ranges:
            msg_err = ("Reserved range >{}< is already present in the topology. Or have overlapped IPs with an existing"
                       "range. See IPv4ReservedRange for more info.").format(reserved_range.model_dump())
            raise ValueError(msg_err)
        self.reserved_ranges.append(reserved_range)
        return reserved_range

    def reserve_range(self, owner: str, length: int, assigned_to: str) -> List[IPv4ReservedRange]:
        """
        Looks into the allocation pool and reserve the desired number of IPs in the reserved ranges.
        Args:
            owner: The owner of the reserved range. Could be the Blueprint ID or the Kubernetes cluster ID for example.
            length: The length of the range to be reserved
            assigned_to: synthetic field that describes the owner of the range

        Returns:
            A list of reserved ranges that ensure the desired length of ips. In the ideal case, only one range is returned (in a list).

        Raises: ValueError if the requested range is too long for the network. There are not enough free IPs.
        """
        total_ips = sum([pool.range_length() for pool in self.allocation_pool])
        available_ips = []
        if total_ips < length:
            raise ValueError("The requested range is too long for the network. There are not enough free IPs.")
        # Building a list of NOT reserved ips.
        for pool in self.allocation_pool:
            if len(available_ips) >= length:
                break
            for ip in pool.ip_list():
                if len(available_ips) >= length:
                    break
                if not self.is_ip_reserved(ip):
                    available_ips.append(ip)
        if len(available_ips) < length:
            raise ValueError("The requested range is too long for the network. There are not enough free IPs.")
        # Start building the reserved range
        reserved_ranges = []
        for ip in available_ips:
            if len(reserved_ranges) == 0:
                reserved_ranges.append(IPv4ReservedRange(start=ip, end=ip, owner=owner, assigned_to=PoolAssignation.K8S_CLUSTER))
            else:
                if reserved_ranges[-1].end + 1 == ip:
                    reserved_ranges[-1].extend_range_end(ip)
                else:
                    reserved_ranges.append(IPv4ReservedRange(start=ip, end=ip, owner=owner, assigned_to=PoolAssignation.K8S_CLUSTER))
        self.reserved_ranges.extend(reserved_ranges)
        return reserved_ranges

    def is_ip_reserved(self, ip: SerializableIPv4Address):
        """
        Check if an IP is reserved in the network
        Args:
            ip: The IP to be checked

        Returns:
            True if the IP is reserved, False otherwise
        """
        for reserved_range in self.reserved_ranges:
            if reserved_range.is_ip_in_range(ip):
                return True
        return False

    def release_range(self, reserved_range_name: str) -> IPv4ReservedRange:
        """
        Release a reserved range in a network Model.
        Args:
            reserved_range_name: The name of the reserved range to be removed

        Returns:
            The released range.
        """
        # Looking for the reservation to be removed in every reserved range.
        for reserved_range in self.reserved_ranges:
            if reserved_range.name == reserved_range_name:
                self.reserved_ranges.remove(reserved_range)
                return reserved_range

        raise ValueError(f"Reserved range >{reserved_range_name}< is not present in the network.")


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
