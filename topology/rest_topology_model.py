from pydantic import BaseModel, HttpUrl, Field, conlist
from typing import List, Optional
from enum import Enum
from ipaddress import IPv4Network, IPv4Address


class VimTypeEnum(str, Enum):
    openstack: str = 'openstack'


class NetworkTypeEnum(str, Enum):
    vlan: str = 'vlan'
    vxlan: str = 'vxlan'
    gre: str = 'gre'
    flat: str = 'flat'

class NfvoOnboardStatus(str, Enum):
    onboarded: str = 'onboarded'
    not_onboarded: str = 'not_onboarded'
    pending: str = 'pending'


class VimModel(BaseModel):
    class VimConfigModel(BaseModel):
        # class VimAdditionalProperties(BaseModel):
        insecure: bool = True
        APIversion: str = 'v3.3'
        use_floating_ip: bool = False
        # additionalProp1: VimAdditionalProperties

    name: str
    vim_type: VimTypeEnum = 'openstack'
    schema_version: str = '1.3'
    vim_url: HttpUrl
    vim_tenant_name: str = 'admin'
    vim_user: str = 'admin'
    vim_password: str = 'admin'
    config: VimConfigModel = {'additionalProp1': {'insecure': True, 'APIversion': 'v3.3'}}
    networks: List[str] = []
    routers: List[str] = []
    areas: List[int] = []


class UpdateVimModel(BaseModel):
    name: str
    networks_to_add: List[str] = Field(
        [],
        description="List of network names declared in the topology to be added to the VIM"
    )
    networks_to_del: List[str] = Field(
        [],
        description="List of network names declared in the topology to be deleted to the VIM"
    )
    routers_to_add: List[str] = Field(
        [],
        description="List of router names declared in the topology to be added to the VIM"
    )
    routers_to_del: List[str] = Field(
        [],
        description="List of router names declared in the topology to be added to the VIM"
    )
    areas_to_add: List[str] = Field(
        [],
        description="List of served area identifiers declared in the topology to be added to the VIM"
    )
    areas_to_del: List[str] = Field(
        [],
        description="List of served area identifiers declared in the topology to be added to the VIM"
    )


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
    nfvo_onboarded: bool =False
    implementation: str
    config: dict
    interface: conlist(PduInterface, min_items=1)


class K8sModel(BaseModel):
    name: str
    provided_by: str
    blueprint_ref: Optional[str]
    credentials: dict
    vim_name: str
    k8s_version: str
    networks: conlist(str, min_items=1)
    areas: conlist(int, min_items=1)
    cni: Optional[str]
    nfvo_status: NfvoOnboardStatus = 'not_onboarded'


class K8sModelCreateFromExternalCluster(BaseModel):
    name: str
    nfvo_onboard: bool = False
    credentials: dict
    vim_name: str
    k8s_version: str
    networks: conlist(str, min_items=1)
    areas: conlist(int, min_items=1)
    cni: Optional[str]

class K8sModelUpdateRequest(BaseModel):
    nfvo_onboard: bool = False
    networks: conlist(str, min_items=1)
    areas: conlist(int, min_items=1)


class K8sModelCreateFromBlueprint(BaseModel):
    name: str
    nfvo_onboard: bool = False
    blueprint_ref: str


class TopologyModel(BaseModel):
    id: Optional[str] = "topology"
    callback: Optional[HttpUrl] = None
    vims: List[VimModel] = []
    kubernetes: List[K8sModel] = []
    networks: List[NetworkModel] = []
    routers: List[RouterModel] = []
    pdus: List[PduModel] = []
