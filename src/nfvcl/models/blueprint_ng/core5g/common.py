from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, constr, HttpUrl
from enum import Enum
from typing import List, Optional, Dict
from pydantic import Field
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint.blueprint_base_model import BlueNSD, BlueprintBaseModel
from nfvcl.models.vim.vim_models import VimModel



# ===================================== SubClasses of subconfig section ================================================
class Pool(BaseModel):
    cidr: str


class SubDataNets(BaseModel):
    net_name: str = Field(..., description="set net-name, exp: 'boh'")
    dnn: str = Field(..., description="set dnn, exp: 'internet'")
    dns: str
    pools: List[Pool]
    uplinkAmbr: Optional[str] = Field(default=None)
    downlinkAmbr: Optional[str] = Field(default=None)
    default5qi: Optional[str] = Field(default=None)


class NetworkEndPoints(BaseModel):
    mgt: Optional[str] = Field(default=None)
    wan: Optional[str] = Field(default=None)
    n3: Optional[str] = Field(default=None)
    n6: Optional[str] = Field(default=None)
    data_nets: List[SubDataNets]


class SubFlows(BaseModel):
    flowId: str = Field(..., description="set flow Id, exp: f0")
    ipAddrFilter: Optional[str] = Field(None, description="set IP address filter")
    qi: constr(pattern=r"[0-9]")
    gfbr: Optional[str] = Field(default=None, description="set gfbr, exp: 100Mbps")


class SubpduSessions(BaseModel):
    pduSessionId: str = Field(..., description="set pduSession Id, exp: p0")
    pduSessionAmbr: Optional[str] = Field(default=None, description="set pduSessionAmbr, exp: 10Mbps")
    flows: List[SubFlows] = Field(default=[])


class SubProfileParams(BaseModel):
    isolationLevel: Literal["ISOLATION", "NO_ISOLATION"]
    sliceAmbr: Optional[str] = Field('1000Mbps', description="Set sliceAmbr, exp: 1000Mbps")
    ueAmbr: Optional[str] = Field('50Mbps', description="Set ueAmbr, exp: 50Mbps")
    maximumNumberUE: Optional[int] = Field(default=None)
    pduSessions: List[SubpduSessions]


class SubLocationConstraints(BaseModel):
    geographicalAreaId: str
    # fixme: Double check for the length
    tai: constr(pattern=r"^[0-9]+$") = Field(..., min_length=10, max_length=11)


class SubEnabledUEList(BaseModel):
    ICCID: str = Field("*", description="set the ICCID")


class SubSliceProfiles(BaseModel):
    sliceId: constr(to_upper=True) = Field(pattern=r'^([a-fA-F0-9]{6})$')
    sliceType: Literal["EMBB", "URLLC", "MMTC"]
    dnnList: List[str] = Field([], description="set dnn-list as a listst on names")
    profileParams: SubProfileParams
    locationConstraints: List[SubLocationConstraints]
    enabledUEList: List[SubEnabledUEList]


class SubSnssai(BaseModel):
    sliceId: constr(to_upper=True) = Field(pattern=r'^([a-fA-F0-9]{6})$')
    sliceType: Literal["EMBB", "URLLC", "MMTC"]
    pduSessionIds: List[str] = Field(..., description="Set Default slices parameters, exp: ['p0', 'p1']")
    default_slice: Optional[bool] = Field(default=None)


class SubSubscribers(BaseModel):
    imsi: str = Field(pattern=r'^[0-9]*$', min_length=15, max_length=15)
    k: str = Field(pattern=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    opc: str = Field(pattern=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    snssai: List[SubSnssai]
    authenticationMethod: Optional[str] = Field(default="5G_AKA")
    authenticationManagementField: Optional[str] = Field(default="8000")


class SubConfig(BaseModel):
    network_endpoints: NetworkEndPoints
    plmn: str = Field(..., pattern=r'^[0-9]*$', min_length=5, max_length=6,
                      description='PLMN identifier of the mobile network'
                      )
    sliceProfiles: Optional[List[SubSliceProfiles]] = Field(default=None, description="Set Default slices parameters")
    subscribers: List[SubSubscribers]


# =================================================== End of Config class =============================================
# ====================================================sub area SubClasses =============================================

class SubSlices(BaseModel):
    sliceType: Literal["EMBB", "URLLC", "MMTC"]
    sliceId: constr(to_upper=True) = Field(pattern=r'^([a-fA-F0-9]{6})$')


class SubArea(BaseModel):
    id: int
    nci: str
    idLength: int
    core: bool = Field(default=True)
    slices: Optional[List[SubSlices]] = Field(default=[], description="set slices ")


# ===============================================end of sub area ======================================================
# =============================================== main section for blue free5gc k8s model class========================


class Create5gModel(BaseModel):
    type: Literal["5G"]
    callbackURL: Optional[HttpUrl] = Field(
        default=None,
        description='url that will be used to notify when the topology terraform ends'
    )
    config: SubConfig
    areas: List[SubArea] = Field(..., description="Set area")


# =========================================== End of main section =====================================================


class AddTacModel(Create5gModel):
    callbackURL: Optional[HttpUrl] = Field(default=None, description="URL that will be used to notify when the topology terraform ends")
    config: Optional[SubConfig] = Field(default=None)


class SubAreaOnlyId(BaseModel):
    id: int


class SstConvertion():
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


class Area5GTypeEnum(Enum):
    CORE = "core"
    EDGE = "edge"
    RAN = "ran"


class Area5G(NFVCLBaseModel):
    """
    Base class that define an Area for 5G blueprints
    """
    id: int
    type: Area5GTypeEnum
    nsd: Optional[BlueNSD] = Field(default=None)


class CoreArea5G(Area5G):
    """
    Class that define a core area for 5G blueprints

    amf_ip: IP address of the amf core function, needs to be reachable by the gnb
    """
    type: Area5GTypeEnum = Area5GTypeEnum.CORE
    amf_ip: Optional[str] = Field(default=None)


class EdgeArea5G(Area5G):
    """
    Class that define a edge area for 5G blueprints

    upf_mgt_ip: IP address of the mgt interface of the UPF vm in this area
    upf_data_ip: IP address of the data interface of the UPF vm in this area
    upf_data_network_cidr: CIDR of the data network
    upf_ue_ip_pool: Pool of IP to use for UEs connecting to this area
    """
    type: Area5GTypeEnum = Area5GTypeEnum.EDGE
    upf_mgt_ip: Optional[str] = Field(default=None)
    upf_data_ip: Optional[str] = Field(default=None)
    upf_data_network_cidr: Optional[str] = Field(default=None)
    upf_ue_ip_pool: Optional[str] = Field(default=None)
    upf_dnn: Optional[str] = Field(default=None)


class RanArea5G(Area5G):
    """
    Class that define a edge area for 5G blueprints

    nb_mgt_ip: IP address of the mgt interface of the GNB vm in this area
    nb_wan_ip: IP address of the data interface of the GNB vm in this area
    """
    type: Area5GTypeEnum = Area5GTypeEnum.RAN
    nb_mgt_ip: Optional[str] = Field(default=None)
    nb_wan_ip: Optional[str] = Field(default=None)


class Networks5G(NFVCLBaseModel):
    wan: str
    mgt: str


class Blueprint5GBaseModel(BlueprintBaseModel):
    """
    Class that contains additional blueprint data that need to be saved in NFVCL's database
    """
    blue_model_5g: Optional[Create5gModel] = Field(default=None)
    core_vim: Optional[VimModel] = Field(default=None)
    networks_5g: Optional[Networks5G] = Field(default=None)
    core_area: Optional[CoreArea5G] = Field(default=None)
    edge_areas: Dict[int, EdgeArea5G] = {}
    ran_areas: Dict[int, RanArea5G] = {}
