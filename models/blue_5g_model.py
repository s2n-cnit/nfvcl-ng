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


class Free5gck8sBlueCreateModel(BaseModel):
    type: Literal['5G']
    callbackURL: Optional[HttpUrl] = Field(
        '',
        description='url that will be used to notify when the topology terraform ends'
    )
    config: Config5G
    # Fixme: Are you sure areas can be empty ? each one doesnt belong to a area?
    areas: list[FiveGAreaInfo] = Field([], description="Set area")

    class Config:
        use_enum_values = True
