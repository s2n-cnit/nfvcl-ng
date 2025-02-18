from __future__ import annotations

from enum import Enum
from typing import List, Optional
from typing import Literal

from pydantic import Field, field_validator

from nfvcl_models.blueprint_ng.g5.custom_types_5g import SDType, SSTType, BitrateStringType, DNNType, OPCType, KEYType, IMSIType, PLMNType
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.custom_types import AreaIDType
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address, SerializableIPv4Network


# ===================================== SubClasses of subconfig section ================================================
class Pool(NFVCLBaseModel):
    cidr: str

class SubDataNets(NFVCLBaseModel):
    net_name: str = Field(description="Name of the network, currently unused")
    dnn: DNNType = Field(description="Name of the DNN")
    dns: str = Field(description="DNS server IP address")
    pools: List[Pool] = Field(default_factory=list, description="List of IP pools for the DNN")
    uplinkAmbr: Optional[BitrateStringType] = Field(default=None, description="Uplink Aggregate Maximum Bit Rate")
    downlinkAmbr: Optional[BitrateStringType] = Field(default=None, description="Downlink Aggregate Maximum Bit Rate")
    default5qi: Optional[str] = Field(default=None)

class Router5GNetworkInfo(NFVCLBaseModel):
    n3_ip: SerializableIPv4Address = Field()
    n6_ip: SerializableIPv4Address = Field()
    gnb_ip: SerializableIPv4Address = Field()
    gnb_cidr: SerializableIPv4Network = Field()

class MultusRoute(NFVCLBaseModel):
    dst: str = Field(description="Destination network CIDR")
    gw: str = Field(description="Gateway IP address")

class NetworkEndPointType(str, Enum):
    MULTUS = "MULTUS"
    LB = "LB" # Load Balancer

class NetworkEndPoint(NFVCLBaseModel):
    net_name: str = Field(description="Name of the network, need to be present in the topology")
    routes: Optional[List[MultusRoute]] = Field(default_factory=list, description="Optional routes for the network")

class NetworkEndPointWithType(NetworkEndPoint):
    type: Optional[NetworkEndPointType] = Field(default=NetworkEndPointType.LB, description="Type of the network endpoint, default is Load Balancer. If this network is used for a VM the type is ignored")

class NetworkEndPoints(NFVCLBaseModel):
    mgt: Optional[NetworkEndPoint] = Field(default=None, description="Used as the management network for VMs, if everything is on K8S this is not needed")
    n2: Optional[NetworkEndPointWithType] = Field(default=None, description="Network endpoint for N2 interface, can be omitted if the core has a fixed network (like Athonet)")
    n4: Optional[NetworkEndPointWithType] = Field(default=None, description="Network endpoint for N4 interface, can be omitted if the core has a fixed network (like Athonet)")
    data_nets: List[SubDataNets] = Field(default_factory=list, description="List of data networks (DNN)", min_length=1)

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
    flowId: str = Field(description="ID of the flow")
    ipAddrFilter: Optional[str] = Field(default=None, description="IP address filter to match this flow")
    qi: str = Field(pattern=r"[0-9]", description="5QI value for this flow")
    gfbr: Optional[BitrateStringType] = Field(default=None, description="Guaranteed Flow Bit Rate, exp: 10 Mbps")


class SubpduSessions(NFVCLBaseModel):
    pduSessionId: str = Field(description="ID of the PDU session")
    pduSessionAmbr: Optional[BitrateStringType] = Field(default=None, description="Aggregate Maximum Bit Rate for this PDU session, exp: 10 Mbps")
    flows: List[SubFlows] = Field(default_factory=list, description="List of flows for this PDU session")


class SubProfileParams(NFVCLBaseModel):
    isolationLevel: Literal["ISOLATION", "NO_ISOLATION"]
    sliceAmbr: Optional[BitrateStringType] = Field(default='1000 Mbps', description="Aggregate Maximum Bit Rate for this slice, exp: 1000 Mbps")
    ueAmbr: Optional[BitrateStringType] = Field(default='50 Mbps', description="Aggregate Maximum Bit Rate for each UE on this slice, exp: 50 Mbps")
    maximumNumberUE: Optional[int] = Field(default=None, description="Maximum number of UEs on this slice")
    pduSessions: List[SubpduSessions] = Field(default_factory=list, description="List of PDU sessions for this slice")


class SubLocationConstraints(NFVCLBaseModel):
    geographicalAreaId: str
    # fixme: Double check for the length
    tai: str = Field(pattern=r"^[0-9]+$", min_length=10, max_length=11, description="Tracking Area Identity, constructed from: MCC, MNC and TAC.")


class SubEnabledUEList(NFVCLBaseModel):
    ICCID: str = Field("*", description="ICCID")


class SubSliceProfiles(NFVCLBaseModel):
    area_ids: Optional[List[str]] = Field(default=None)
    sliceId: SDType = Field(description="Slice ID (SD)")
    sliceType: SSTType = Field(description="Slice Type (SST)")
    dnnList: List[str] = Field(default_factory=list, description="List of DNN available for this slice, the DNN must be present in the data_nets list")
    profileParams: SubProfileParams = Field(description="QoS for this slice")
    locationConstraints: Optional[List[SubLocationConstraints]] = Field(default_factory=list, description="Location constraints for this slice, CURRENTLY UNUSED")
    enabledUEList: Optional[List[SubEnabledUEList]] = Field(default_factory=list, description="List of enabled UEs for this slice, CURRENTLY UNUSED")


class SubSnssai(NFVCLBaseModel):
    sliceId: SDType = Field(description="Slice ID (SD)")
    sliceType: SSTType = Field(description="Slice Type (SST)")
    pduSessionIds: List[str] = Field(default_factory=list, description="List of PDU session IDs for this SNSSAI, need to be present in the pduSessions list of the corresponding slice profile")
    default_slice: Optional[bool] = Field(default=None, description="Set this slice as the default for the subscriber")


class SubSubscribers(NFVCLBaseModel):
    imsi: IMSIType = Field()
    k: KEYType = Field()
    opc: OPCType = Field()
    snssai: List[SubSnssai] = Field(default_factory=list, description="List of slices for this subscriber")
    authenticationMethod: Optional[str] = Field(default="5G_AKA")
    authenticationManagementField: Optional[str] = Field(default="8000")


class SubPersistence(NFVCLBaseModel):
    enabled: bool = Field(default=True)
    storageClass: Optional[str] = Field(default="")

class SubConfig(NFVCLBaseModel):
    network_endpoints: NetworkEndPoints
    plmn: PLMNType = Field(description="PLMN identifier of the mobile network")
    sliceProfiles: Optional[List[SubSliceProfiles]] = Field(default=None, description="Slices for this core")
    subscribers: List[SubSubscribers] = Field(default_factory=list, description="List of subscribers")
    persistence: Optional[SubPersistence] = Field(default_factory=SubPersistence, description="Persistence configuration for the core")


# =================================================== End of Config class =============================================
# ====================================================sub area SubClasses =============================================

class SubSlices(NFVCLBaseModel):
    sliceType: SSTType
    sliceId: SDType

class SubAreaNetwork(NFVCLBaseModel):
    n3: Optional[NetworkEndPointWithType] = Field(default=None, description="Network endpoint for N3 interface")
    n6: Optional[NetworkEndPointWithType] = Field(default=None, description="Network endpoint for N6 interface")
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
    id: AreaIDType = Field(description="ID of the area")
    # TODO need validator
    nci: str = Field(description="NR Cell Identity in hex format")
    idLength: int = Field(description="Length of the NCI in bits", default=36, ge=32, le=36)
    core: bool = Field(default=True, description="Set this area as the core area, only one area can be set as core")
    gnb: Optional[SubAreaGNB] = Field(default_factory=SubAreaGNB, description="Additional GNB configuration")
    upf: Optional[SubAreaUPF] = Field(default_factory=SubAreaUPF, description="Additional UPF configuration")
    networks: SubAreaNetwork = Field(description="Network configuration specific for this area")
    slices: Optional[List[SubSlices]] = Field(default_factory=list, description="List of slices for this area")


# ===============================================end of sub area ======================================================
# =============================================== main section for blue free5gc k8s model class========================


class Create5gModel(NFVCLBaseModel):
    config: SubConfig = Field(description="Core configuration")
    areas: List[SubArea] = Field(description="Areas configuration")

    def get_area(self, area_id: int):
        for area in self.areas:
            if area.id == area_id:
                return area
        return None

    def get_slice_profile(self, slice_id: str) -> Optional[SubSliceProfiles]:
        for slice in self.config.sliceProfiles:
            if slice.sliceId == slice_id:
                return slice
        return None

    def get_slices_profiles_for_area(self, area_id: int) -> List[SubSliceProfiles]:
        slice_profiles: List[SubSliceProfiles] = []
        for area in self.areas:
            if area.id == area_id:
                for slice in area.slices:
                    slice_profiles.append(self.get_slice_profile(slice.sliceId))
        return slice_profiles

# =========================================== End of main section =====================================================
