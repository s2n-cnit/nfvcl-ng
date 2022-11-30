from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, IPvAnyAddress, IPvAnyNetwork,\
    Field, constr, HttpUrl


# ===================================== SubClasses of subconfig section ================================================
class SubDataNets(BaseModel):
    net_name: str = Field(..., description="set net-name, exp: 'boh'")
    dnn: str = Field(..., description="set dnn, exp: 'internet'")


class NetworkEndPoints(BaseModel):
    mgt: Optional[str] = None
    wan: Optional[str] = None
    data_nets: List[SubDataNets]


class SubFlows(BaseModel):
    flowId: str = Field(..., description="set flow Id, exp: f0")
    ipAddrFilter: IPvAnyAddress = Field(None, description="set IP address filter")
    fiveqi: constr(regex=r"[0-9]") = Field(..., alias="5qi")
    gfbr: Optional[str] = Field(..., description="set gfbr, exp: 100Mbps")


class SubpduSessions(BaseModel):
    pduSessionId: str = Field(..., description="set pduSession Id, exp: p0")
    pduSessionAmbr: Optional[str] = Field(..., description="set pduSessionAmbr, exp: 10Mbps")
    flows: List[SubFlows]


class SubProfileParams(BaseModel):
    isolationLevel: Literal["ISOLATION", "NO_ISOLATION"]
    sliceAmbr: Optional[str] = Field('1000Mbps', description="Set sliceAmber, exp: 1000Mbps")
    ueAmbr: Optional[str] = Field('50Mbps', description="Set ueAmbr, exp: 50Mbps")
    maximumNumberUE: Optional[int]
    pduSessions: List[SubpduSessions]


class SubLocationConstraints(BaseModel):
    geographicalAreaId: str
    # fixme: Double check for the length
    tai: constr(regex=r"^[0-9]+$") = Field(..., min_length=10, max_length=11)


class SubEnabledUEList(BaseModel):
    ICCID: str = Field("*", description="set the ICCID")


class SubSliceProfiles(BaseModel):
    sliceId: str
    sliceType: Literal["EMBB", "URLLC", "MMTC"]
    dnnlist: List[str] = Field([], description="set dnn-list as a listst on names")
    profileParams: SubProfileParams
    locationConstraints: List[SubLocationConstraints]
    enabledUEList: List[SubEnabledUEList]


class SubSnssai(BaseModel):
    sliceId: str
    sliceType: Literal["EMBB", "URLLC", "MMTC"]
    pduSessionIds: List[str] = Field(..., description="Set Default slices parameters, exp: ['p0', 'p1']")
    default_slice: Optional[bool]


class SubSubscribers(BaseModel):
    imsi: constr(regex=r'^[0-9]*$', min_length=15, max_length=15)
    k: constr(regex=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    opc: constr(regex=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    snssai: List[SubSnssai]


class SubConfig(BaseModel):
    network_endpoints: NetworkEndPoints
    plmn: constr(regex=r'^[0-9]*$', min_length=5, max_length=6) = Field(
        ...,
        description='PLMN identifier of the mobile network'
    )
    sliceProfiles: Optional[List[SubSliceProfiles]] = Field(..., description="Set Default slices parameters")
    subscribers: List[SubSubscribers]


# =================================================== End of Config class =============================================
# ====================================================sub area SubClasses =============================================
class Pool(BaseModel):
    cidr: IPvAnyNetwork

class DnnElem(BaseModel):
    dnn: str
    dns: str
    pools: List[Pool]


class SubSlices(BaseModel):
    sst: int
    sd: str
    dnnList: List[DnnElem]


class SubArea(BaseModel):
    id: int
    nci: str
    idLength: int
    core: bool
    slices: Optional[List[SubSlices]] = Field([],description="set slices ")
# ===============================================end of sub area ======================================================
# =============================================== main section for blue free5gc k8s model class========================


class Create5gModel(BaseModel):
    type: Literal["5G"]
    callbackURL: Optional[HttpUrl] = Field(
        '',
        description='url that will be used to notify when the topology terraform ends'
    )
    config: SubConfig
    areas: List[SubArea] = Field(..., description="Set area")

# =========================================== End of main section =====================================================


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