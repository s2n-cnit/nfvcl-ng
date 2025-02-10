from __future__ import annotations

from enum import Enum
from typing import List, Optional
from typing import Literal

from pydantic import Field, field_validator
from pydantic import constr

from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.network.ipam_models import SerializableIPv4Address, SerializableIPv4Network


# ===================================== SubClasses of subconfig section ================================================
class Pool(NFVCLBaseModel):
    cidr: str

class SubDataNets(NFVCLBaseModel):
    net_name: str = Field(..., description="set net-name, exp: 'internet'")
    dnn: str = Field(..., description="set dnn, exp: 'internet'")
    dns: str
    pools: List[Pool]
    uplinkAmbr: Optional[str] = Field(default=None)
    downlinkAmbr: Optional[str] = Field(default=None)
    default5qi: Optional[str] = Field(default=None)

class Router5GNetworkInfo(NFVCLBaseModel):
    n3_ip: SerializableIPv4Address = Field()
    n6_ip: SerializableIPv4Address = Field()
    gnb_ip: SerializableIPv4Address = Field()
    gnb_cidr: SerializableIPv4Network = Field()

class MultusRoute(NFVCLBaseModel):
    dst: str
    gw: str

class NetworkEndPointType(str, Enum):
    MULTUS = "MULTUS"
    LB = "LB" # Load Balancer

class NetworkEndPoint(NFVCLBaseModel):
    net_name: str = Field(description="Name of the network, need to be present in the topology")
    routes: Optional[List[MultusRoute]] = Field(default_factory=list)

class NetworkEndPointWithType(NetworkEndPoint):
    type: Optional[NetworkEndPointType] = Field(default=NetworkEndPointType.LB, description="Type of the network endpoint, default is Load Balancer. If this network is used for a VM the type is ignored")

class NetworkEndPoints(NFVCLBaseModel):
    mgt: Optional[NetworkEndPoint] = Field(default=None, description="Used as the management network for VMs, if everything is on K8S this is not needed")
    n2: Optional[NetworkEndPointWithType] = Field(default=None, description="Network endpoint for N2 interface, can be omitted if the core has a fixed network (like Athonet)")
    n4: Optional[NetworkEndPointWithType] = Field(default=None, description="Network endpoint for N4 interface, can be omitted if the core has a fixed network (like Athonet)")
    data_nets: List[SubDataNets]

    @field_validator("mgt", mode="before")
    def str_to_network_endpoint(cls, v: object) -> object:
        if isinstance(v, str):
            return NetworkEndPoint(net_name=v)
        return v

    @field_validator("n2", "n4", mode="before")
    def str_to_network_endpoint_with_type(cls, v: object) -> object:
        if isinstance(v, str):
            return NetworkEndPointWithType(net_name=v)
        return v


class SubFlows(NFVCLBaseModel):
    flowId: str = Field(..., description="set flow Id, exp: f0")
    ipAddrFilter: Optional[str] = Field(None, description="set IP address filter")
    qi: constr(pattern=r"[0-9]")
    gfbr: Optional[str] = Field(default=None, description="set gfbr, exp: 100Mbps")


class SubpduSessions(NFVCLBaseModel):
    pduSessionId: str = Field(..., description="set pduSession Id, exp: p0")
    pduSessionAmbr: Optional[str] = Field(default=None, description="set pduSessionAmbr, exp: 10Mbps")
    flows: List[SubFlows] = Field(default=[])


class SubProfileParams(NFVCLBaseModel):
    isolationLevel: Literal["ISOLATION", "NO_ISOLATION"]
    sliceAmbr: Optional[str] = Field('1000Mbps', description="Set sliceAmbr, exp: 1000Mbps")
    ueAmbr: Optional[str] = Field('50Mbps', description="Set ueAmbr, exp: 50Mbps")
    maximumNumberUE: Optional[int] = Field(default=None)
    pduSessions: List[SubpduSessions]


class SubLocationConstraints(NFVCLBaseModel):
    geographicalAreaId: str
    # fixme: Double check for the length
    tai: constr(pattern=r"^[0-9]+$") = Field(..., min_length=10, max_length=11)


class SubEnabledUEList(NFVCLBaseModel):
    ICCID: str = Field("*", description="set the ICCID")


class SubSliceProfiles(NFVCLBaseModel):
    area_ids: Optional[List[str]] = Field(default=None)
    sliceId: constr(to_upper=True) = Field(pattern=r'^([a-fA-F0-9]{6})$')
    sliceType: Literal["EMBB", "URLLC", "MMTC"]
    dnnList: List[str] = Field([], description="set dnn-list as a listst on names")
    profileParams: SubProfileParams
    locationConstraints: Optional[List[SubLocationConstraints]] = Field(default_factory=list)
    enabledUEList: Optional[List[SubEnabledUEList]] = Field(default_factory=list)


class SubSnssai(NFVCLBaseModel):
    sliceId: constr(to_upper=True) = Field(pattern=r'^([a-fA-F0-9]{6})$')
    sliceType: Literal["EMBB", "URLLC", "MMTC"]
    pduSessionIds: List[str] = Field(..., description="Set Default slices parameters, exp: ['p0', 'p1']")
    default_slice: Optional[bool] = Field(default=None)


class SubSubscribers(NFVCLBaseModel):
    imsi: str = Field(pattern=r'^[0-9]*$', min_length=15, max_length=15)
    k: str = Field(pattern=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    opc: str = Field(pattern=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    snssai: List[SubSnssai]
    authenticationMethod: Optional[str] = Field(default="5G_AKA")
    authenticationManagementField: Optional[str] = Field(default="8000")


class SubPersistence(NFVCLBaseModel):
    enabled: bool = Field(default=True)
    storageClass: Optional[str] = Field(default="")

class SubConfig(NFVCLBaseModel):
    network_endpoints: NetworkEndPoints
    plmn: str = Field(..., pattern=r'^[0-9]*$', min_length=5, max_length=6,
                      description='PLMN identifier of the mobile network'
                      )
    sliceProfiles: Optional[List[SubSliceProfiles]] = Field(default=None, description="Set Default slices parameters")
    subscribers: List[SubSubscribers]
    persistence: Optional[SubPersistence] = Field(default_factory=SubPersistence)


# =================================================== End of Config class =============================================
# ====================================================sub area SubClasses =============================================

class SubSlices(NFVCLBaseModel):
    sliceType: Literal["EMBB", "URLLC", "MMTC"]
    sliceId: constr(to_upper=True) = Field(pattern=r'^([a-fA-F0-9]{6})$')

class SubAreaNetwork(NFVCLBaseModel):
    n3: Optional[NetworkEndPointWithType] = Field(default=None, description="Network endpoint for N3 interface")
    n6: Optional[NetworkEndPointWithType] = Field(default=None, description="Network endpoint for N3 interface")
    gnb: Optional[NetworkEndPoint] = Field(default=None, description="Network endpoint for GNB network, only required if a router is needed for this UPF configuration")
    external_router: Optional[Router5GNetworkInfo] = Field(default=None)

    @field_validator("gnb", mode="before")
    def str_to_network_endpoint(cls, v: object) -> object:
        if isinstance(v, str):
            return NetworkEndPoint(net_name=v)
        return v

    @field_validator("n3", "n6", mode="before")
    def str_to_network_endpoint_with_type(cls, v: object) -> object:
        if isinstance(v, str):
            return NetworkEndPointWithType(net_name=v)
        return v

class SubAreaUPF(NFVCLBaseModel):
    type: Optional[str] = Field(default=None)
    external: Optional[bool] = Field(default=False)

class SubAreaGNB(NFVCLBaseModel):
    configure: bool = Field(default=True)
    pduList: Optional[List[str]] = Field(default=None)

class SubArea(NFVCLBaseModel):
    id: int
    nci: str
    idLength: int
    core: bool = Field(default=True)
    gnb: Optional[SubAreaGNB] = Field(default_factory=SubAreaGNB)
    upf: Optional[SubAreaUPF] = Field(default_factory=SubAreaUPF)
    networks: SubAreaNetwork = Field()
    slices: Optional[List[SubSlices]] = Field(default=[], description="set slices ")


# ===============================================end of sub area ======================================================
# =============================================== main section for blue free5gc k8s model class========================


class Create5gModel(NFVCLBaseModel):
    config: SubConfig
    areas: List[SubArea] = Field(..., description="Set area")

    def get_area(self, area_id: int):
        for area in self.areas:
            if area.id == area_id:
                return area
        return None

    def get_slice_profile(self, slice_id: str) -> SubSliceProfiles:
        for slice in self.config.sliceProfiles:
            if slice.sliceId == slice_id:
                return slice

    def get_slices_profiles_for_area(self, area_id: int) -> List[SubSliceProfiles]:
        slice_profiles: List[SubSliceProfiles] = []
        for area in self.areas:
            if area.id == area_id:
                for slice in area.slices:
                    slice_profiles.append(self.get_slice_profile(slice.sliceId))
        return slice_profiles



# =========================================== End of main section =====================================================

class SstConvertion:
    sstType = {"EMBB": 1, "URLLC": 2, "MMTC": 3}

    def __init__(self) -> None:
        pass

    @classmethod
    def to_string(cls, value: int = None) -> str:
        return next((k for k, v in cls.sstType.items() if v == value), None)

    @classmethod
    def to_int(cls, value: str = None) -> int:
        return next((v for k, v in cls.sstType.items() if k == value), None)


class NssiConvertion(SstConvertion):
    @classmethod
    def toNssi(cls, fromSlice: SubSlices = None):
        return {"sst": cls.to_int(fromSlice.sliceType), "sd": fromSlice.sliceId}

    @classmethod
    def toSlice(cls, fromNssi: dict = None) -> SubSlices:
        return SubSlices.model_validate({"sliceType": cls.to_string(fromNssi["sst"]), "sliceId": fromNssi["sd"]})  # TODO workaround for Literal type
