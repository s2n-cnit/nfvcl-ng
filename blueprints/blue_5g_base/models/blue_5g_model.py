
from __future__ import annotations

from enum import Enum
from ipaddress import IPv4Address, IPv4Network
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, conlist


class Cni(Enum):
    flannel = 'flannel'
    calico = 'calico'


class LbType(Enum):
    layer2 = 'layer2'
    layer3 = 'layer3'


class LBPool(BaseModel):
    mode: LbType = Field(
        'layer2', description='Operating mode of Metal-LB. Default Layer-2.'
    )
    net_name: str = Field(
        ..., description='name of the network in the topology'
    )
    ip_start: Optional[IPv4Address] = None
    ip_end: Optional[IPv4Address] = None
    range_length: Optional[str] = Field(
        None,
        description='Number of IPv4 addresses to reserved if no ip start and end are passed. Default 10 addresses.',
    )

    class Config:
        use_enum_values = True


class K8sNetworkEndpoints(BaseModel):
    mgt: str = Field(
        ..., description='name of the topology network to be used for management'
    )
    data_nets: List[LBPool] = Field(..., description='topology networks to be used by the load balancer')


class VMFlavors(BaseModel):
    memory_mb: str = Field(16384, alias='memory-mb')
    storage_gb: str = Field(32, alias='storage-gb')
    vcpu_count: str = Field(16, alias='vcpu-count')


class K8sAreaInfo(BaseModel):
    id: int
    core: Optional[bool] = False
    workers_replica: int
    worker_flavor_override: Optional[VMFlavors]


class K8sConfig(BaseModel):
    version: Optional[str] = "1.24"
    cni: Optional[Cni] = "flannel"
    linkerd: Optional[dict]
    pod_network_cidr: Optional[IPv4Network] \
        = Field('10.254.0.0/16', description='K8s Pod network IPv4 cidr to init the cluster')
    network_endpoints: K8sNetworkEndpoints
    worker_flavors: VMFlavors = VMFlavors()
    master_flavors: VMFlavors = VMFlavors()

    class Config:
        use_enum_values = True


class K8sBlueprintCreate(BaseModel):
    type: Literal['K8s']
    callbackURL: Optional[str] = Field(
        None,
        description='url that will be used to notify when the blueprint processing finishes',
    )
    config: K8sConfig
    areas: conlist(K8sAreaInfo, min_items=1) = Field(
        ...,
        description='list of areas to instantiate the Blueprint',
    )

    class Config:
        use_enum_values = True


class Create5gModel(BaseModel):
    callbackURL: Optional[str] = Field(
        None,
        description='url that will be used to notify when the blueprint processing finishes',
    )
    operation: Literal['scale']
    add_areas: List[K8sAreaInfo]
    modify_areas: List[K8sAreaInfo]
    del_areas: List[K8sAreaInfo]



'''
from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel, IPvAnyAddress, Field, constr, HttpUrl
# from ipaddress import IPv4Address


class Flavors(str, Enum):
    flavor_k8s = "k8s"
    flavor_free5gc = "free5gc"


class NetworkEndPoints(BaseModel):
    wan: Optional[str] = None
    mgt: Optional[str] = None


class SubDns(BaseModel):
    ipv4: IPvAnyAddress = Field(..., description="IPv4 for DNS, x.x.x.x")


class SubPools(BaseModel):
    # ToDO: use regex to define exact value, exp, "61.0.0.0/24"
    cidr: str = Field(..., description="exp, x.x.x.x/cidr ")


class FlowRules(BaseModel):
    ipFilter: IPvAnyAddress
    fiveqi: constr(regex=r"[0-9]") = Field(..., alias="5qi")
    uplinkGbr: str = Field(None, description="exp, 100 Mbps")
    downlinkGbr: str = Field(None, description="exp, 100 Mbps")
    uplinkMbr: str = Field(None, description="exp, 100 Mbps")
    downlinkMbr: str = Field(None, description="exp, 100 Mbps")
    upSecurity: bool


class SubDnnList(BaseModel):
    dnn: str
    dns: Optional[SubDns] = None
    pools: Optional[List[SubPools]] = None
    uplinkAmbr: Optional[str] = Field(None, description="exp, 200 Mbps")
    downlinkAmbr: Optional[str] = Field(None, description="exp, 100 Mbps")
    default5qi: Optional[int] = None
    flowRules: Optional[FlowRules] = None


# # Fixme: This is the same as slices, I can set one !
# class SubsnssaiList(BaseModel):
#     sst: int
#     sd: str
#     dnnList: List[SubDnnList]


class Five5SliceRef(BaseModel):
    sst: int
    sd: constr(regex=r'^[0-9][A-F]*$', min_length=6, max_length=6)


class FiveGSlice(Five5SliceRef):
    dnns: List[SubDnnList]


class FiveGSubscribers(BaseModel):
    imsi: constr(regex=r'^[0-9]*$', min_length=15, max_length=15)
    k: constr(regex=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    opc: constr(regex=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    snssai: List[FiveGSlice]
    default_slice: Five5SliceRef


class Config5G(BaseModel):
    plmn: constr(regex=r'^[0-9]*$', min_length=5, max_length=6) = Field(
        ...,
        description='PLMN identifier of the mobile network'
    )
    network_endpoints: NetworkEndPoints
    subscribers: List[FiveGSubscribers]
    sliceProfiles: List[FiveGSlice] = Field([], description="Set Default slices parameters", alias='5g-slices')


class FiveGAreaInfo(BaseModel):
    id: int
    nci: str
    idLength: int
    core: bool
    slices: List[Five5SliceRef]


class Create5gModel(BaseModel):
    type: Literal['5G']
    callbackURL: Optional[HttpUrl] = Field(
        '',
        description='url that will be used to notify when the topology terraform ends'
    )
    config: Config5G
    # Fixme: Are you sure areas can be empty ? each one doesnt belong to a area?
    areas: List[FiveGAreaInfo] = Field([], description="Set area")

    class Config:
        use_enum_values = True
'''