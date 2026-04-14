from __future__ import annotations

import ipaddress
import re
from enum import IntEnum
from typing import List, Optional, Literal

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.network.network_models import MultusInterface
from nfvcl_models.blueprint_ng.core5g.common import SubSliceProfiles, Create5gModel, SubSubscribers
from nfvcl_models.blueprint_ng.g5.common5g import Slice5G
from nfvcl_models.blueprint_ng.g5.custom_types_5g import MCCType, MNCType, IMSIType, KEYType, OPCType, SSTType, SDType


class Image(NFVCLBaseModel):
    registry: str
    repository: str
    tag: str
    pull_policy: str = Field(..., alias='pullPolicy')


class Populate(NFVCLBaseModel):
    enabled: bool
    image: Image
    init_commands: List = Field(..., alias='initCommands')


class Auth(NFVCLBaseModel):
    enabled: bool


class Mongodb(NFVCLBaseModel):
    enabled: bool
    auth: Auth


class NFMongodb(NFVCLBaseModel):
    enabled: bool


class Openg5sDev(NFVCLBaseModel):
    dev: str = Field(default="eth0", alias='dev')


class MultusNetwork(NFVCLBaseModel):
    enabled: bool
    name: str
    type: str
    master_if: str = Field(..., alias='masterIf')
    interface_name: str = Field(..., alias='interfaceName')
    ip_address: str = Field(..., alias='ipAddress')
    subnet_mask: str = Field(..., alias='subnetMask')
    gateway_ip: Optional[str] = Field(..., alias='gatewayIP')

    def set_multus(self, multus_interface: MultusInterface, gateway_ip=None):
        self.enabled = True
        self.type = "macvlan"
        self.ip_address = multus_interface.ip_address.exploded
        self.subnet_mask = str(multus_interface.prefixlen)
        self.gateway_ip = gateway_ip
        self.master_if = multus_interface.host_interface


class SmfMultus(NFVCLBaseModel):
    enabled: bool
    n4network: Optional[MultusNetwork] = None
    network_attachments: List = Field(default_factory=list, alias='networkAttachments')


class AmfMultus(NFVCLBaseModel):
    enabled: bool
    n2network: Optional[MultusNetwork] = None
    network_attachments: List = Field(default_factory=list, alias='networkAttachments')


class PfcpItem(NFVCLBaseModel):
    address: str
    dnn: str


class SmfUpf(NFVCLBaseModel):
    pfcp: List[PfcpItem]


class Frdi(NFVCLBaseModel):
    hostname: str
    port: int


class SmfPcrf(NFVCLBaseModel):
    enabled: bool = Field(default=False)
    frdi: Frdi


class SubnetListItem(NFVCLBaseModel):
    subnet: str
    gateway: str
    dnn: str


class SNssaiItem(Slice5G):
    dnn: List[str]


class PlmnId(NFVCLBaseModel):
    mcc: MCCType
    mnc: MNCType


class TaiItem(NFVCLBaseModel):
    plmn_id: PlmnId
    tac: int


class InfoItem(NFVCLBaseModel):
    s_nssai: List[SNssaiItem]
    tai: List[TaiItem]


class NssfNrf(NFVCLBaseModel):
    enabled: bool
    uri: str


class NssfScp(NFVCLBaseModel):
    enabled: bool
    uri: str


class Client(NFVCLBaseModel):
    nrf: NssfNrf
    scp: Optional[NssfScp] = None


class Sbi(NFVCLBaseModel):
    client: Client


class BaseNFConfig(NFVCLBaseModel):
    log_level: str = Field("debug", alias='logLevel')
    sbi: Sbi


class Service(NFVCLBaseModel):
    type: str = Field(default="ClusterIP", alias='type')


class SmfServices(NFVCLBaseModel):
    sbi: Service = Field(default_factory=Service)
    frdi: Service = Field(default_factory=Service)
    pfcp: Service = Field(default_factory=Service)
    gtpc: Service = Field(default_factory=Service)
    gtpu: Service = Field(default_factory=Service)
    metrics: Service = Field(default_factory=Service)


class AmfServices(NFVCLBaseModel):
    sbi: Service = Field(default_factory=Service)
    ngap: Service = Field(default_factory=Service)
    metrics: Service = Field(default_factory=Service)


class NrfServices(NFVCLBaseModel):
    sbi: Service = Field(default_factory=Service)


class SmfConfig(BaseNFConfig):
    upf: SmfUpf
    pcrf: SmfPcrf
    pfcp: Optional[Openg5sDev] = Field(default_factory=Openg5sDev, alias='pfcp')
    dns_list: List[str] = Field(..., alias='dnsList')
    subnet_list: List[SubnetListItem] = Field(..., alias='subnetList')
    mtu: int
    info: List[InfoItem]


class Smf(NFVCLBaseModel):
    enabled: bool
    multus: Optional[SmfMultus] = None
    config: SmfConfig
    services: Optional[SmfServices] = Field(default_factory=SmfServices)

    def add_upf_addresses(self, upf_ip: str, dnn: str):
        pfcp_item = PfcpItem(
            address=upf_ip,
            dnn=dnn
        )
        self.config.upf.pfcp.append(pfcp_item)

    def add_subnet_item(self, cidr: str, dnn: str):
        ip = ipaddress.ip_network(cidr)
        subnet_item = SubnetListItem(
            subnet=cidr,
            gateway=ip[1].exploded,
            dnn=dnn
        )
        if subnet_item not in self.config.subnet_list:
            self.config.subnet_list.append(subnet_item)

    def add_info_item(self, _slices: List[SubSliceProfiles], area_id: int, mcc: str, mnc: str):
        info_item = InfoItem(
            s_nssai=[],
            tai=[TaiItem(
                plmn_id=PlmnId(
                    mcc=mcc,
                    mnc=mnc
                ),
                tac=area_id
            )]
        )
        for _slice in _slices:
            new_slice = SNssaiItem(
                sst=_slice.sliceType,
                sd=_slice.sliceId,
                dnn=[_slice.dnnList[0]]  # Take only the first dnn
            )
            info_item.s_nssai.append(new_slice)
        self.config.info.append(info_item)


class Upf(NFVCLBaseModel):
    enabled: bool


class Webui(NFVCLBaseModel):
    enabled: bool


class Hss(NFVCLBaseModel):
    enabled: bool
    mongodb: Optional[NFMongodb] = None


class Mme(NFVCLBaseModel):
    enabled: bool


class Pcrf(NFVCLBaseModel):
    enabled: bool
    mongodb: Optional[NFMongodb] = None


class Sgwc(NFVCLBaseModel):
    enabled: bool


class Sgwu(NFVCLBaseModel):
    enabled: bool


class AmfId(NFVCLBaseModel):
    region: int = Field(default=2)
    set: int = Field(default=1)


class GuamiListItem(NFVCLBaseModel):
    plmn_id: PlmnId
    amf_id: Optional[AmfId] = Field(default_factory=AmfId, alias='amf_id')


class TaiListItem(NFVCLBaseModel):
    plmn_id: PlmnId
    tac: List[int]


class PlmnListItem(NFVCLBaseModel):
    plmn_id: PlmnId
    s_nssai: List[Slice5G]


class AmfConfig(BaseNFConfig):
    guami_list: List[GuamiListItem] = Field(..., alias='guamiList')
    tai_list: List[TaiListItem] = Field(..., alias='taiList')
    plmn_list: List[PlmnListItem] = Field(..., alias='plmnList')
    networkname: str = Field("Gradiant", alias='networkName')
    ngap: Optional[Openg5sDev] = Field(default_factory=Openg5sDev)

    def add_guami_list_item(self, mcc: str, mnc: str):
        self.guami_list.append(GuamiListItem(
            plmn_id=PlmnId(
                mcc=mcc,
                mnc=mnc
            )
        ))

    def add_tai_list_item(self, mcc: str, mnc: str, area_id: int):
        self.tai_list.append(TaiListItem(
            plmn_id=PlmnId(
                mcc=mcc,
                mnc=mnc
            ),
            tac=[area_id]
        ))

    def add_plmn_list_item(self, mcc: str, mnc: str, snssai: List[SubSliceProfiles]):
        tmp: List[Slice5G] = []
        for _slice in snssai:
            item = Slice5G(
                sst=_slice.sliceType,
                sd=_slice.sliceId
            )
            tmp.append(item)
        self.plmn_list.append(PlmnListItem(
            plmn_id=PlmnId(
                mcc=mcc,
                mnc=mnc
            ),
            s_nssai=tmp
        ))


class Amf(NFVCLBaseModel):
    enabled: bool
    multus: Optional[AmfMultus] = None
    config: AmfConfig
    services: Optional[AmfServices] = Field(default_factory=AmfServices)


class Ausf(NFVCLBaseModel):
    enabled: bool
    config: BaseNFConfig


class Bsf(NFVCLBaseModel):
    enabled: bool
    config: BaseNFConfig


class ServingListItem(NFVCLBaseModel):
    plmn_id: PlmnId


class NrfConfig(NFVCLBaseModel):
    log_level: str = Field("debug", alias='logLevel')
    serving_list: List[ServingListItem] = Field(..., alias='servingList')


class Nrf(NFVCLBaseModel):
    enabled: bool
    config: NrfConfig
    services: Optional[NrfServices] = Field(default_factory=NrfServices)

    def add_serving_list_item(self, mcc: str, mnc: str):
        self.config.serving_list.append(
            ServingListItem(
                plmn_id=PlmnId(
                    mcc=mcc,
                    mnc=mnc
                )
            ))


class NsiListItem(Slice5G):
    uri: Optional[str] = Field(default="", alias='uri')


class NssfConfig(BaseNFConfig):
    nsi_list: List[NsiListItem] = Field(..., alias='nsiList')


class Nssf(NFVCLBaseModel):
    enabled: bool
    config: NssfConfig

    def add_nsi_list_item(self, snssai: SubSliceProfiles):
        item = NsiListItem(
            sst=snssai.sliceType,
            sd=snssai.sliceId
        )
        if item not in self.config.nsi_list:
            self.config.nsi_list.append(item)


class Pcf(NFVCLBaseModel):
    enabled: bool
    mongodb: NFMongodb
    config: BaseNFConfig


class Scp(NFVCLBaseModel):
    enabled: bool
    mongodb: NFMongodb
    config: BaseNFConfig


class Udm(NFVCLBaseModel):
    enabled: bool
    config: BaseNFConfig


class Udr(NFVCLBaseModel):
    enabled: bool
    config: BaseNFConfig


class Open5gsCoreConfig(NFVCLBaseModel):
    db_uri: Optional[str] = Field(None, alias='dbURI')
    populate: Optional[Populate] = None
    mongodb: Optional[Mongodb] = None
    smf: Optional[Smf] = None
    upf: Optional[Upf] = None
    webui: Optional[Webui] = None
    # hss: Optional[Hss] = None
    # mme: Optional[Mme] = None
    # pcrf: Optional[Pcrf] = None
    # sgwc: Optional[Sgwc] = None
    # sgwu: Optional[Sgwu] = None
    amf: Optional[Amf] = None
    ausf: Optional[Ausf] = None
    bsf: Optional[Bsf] = None
    nrf: Optional[Nrf] = None
    nssf: Optional[Nssf] = None
    pcf: Optional[Pcf] = None
    scp: Optional[Scp] = None
    udm: Optional[Udm] = None
    udr: Optional[Udr] = None


# Subscriber Models
class BitrateUnit(IntEnum):
    """Bitrate units mapping for Open5GS"""
    bps = 0
    kbps = 1
    Mbps = 2
    Gbps = 3


class DataValue(NFVCLBaseModel):
    value: int
    unit: BitrateUnit


class AmbrData(NFVCLBaseModel):
    downlink: DataValue
    uplink: DataValue


class Security(NFVCLBaseModel):
    k: KEYType
    amf: str
    op_type: int
    op_value: str
    op: Optional[str] = None
    opc: OPCType


class Arp(NFVCLBaseModel):
    priority_level: int
    pre_emption_capability: Literal[1, 2]
    pre_emption_vulnerability: Literal[1, 2]


class Qos(NFVCLBaseModel):
    index: int
    arp: Arp


class Session(NFVCLBaseModel):
    name: str
    type: int
    ambr: AmbrData
    qos: Qos


class SubscriberSlice(NFVCLBaseModel):
    sst: SSTType
    sd: Optional[SDType] = None
    default_indicator: bool
    session: List[Session]


class Open5gsSubscriber(NFVCLBaseModel):
    imsi: IMSIType
    security: Security
    ambr: AmbrData
    subscriber_status: int = Field(default=0)
    operator_determined_barring: int = Field(default=0)
    slice: List[SubscriberSlice]

    @classmethod
    def from_create5g_model(cls, subscriber: SubSubscribers, create5g_model: Create5gModel) -> Open5gsSubscriber:
        def parse_bitrate(bitrate_str: str) -> DataValue:
            """Convert bitrate string (e.g., '1 Gbps') to DataValue"""
            match = re.match(r'(\d+(?:\.\d+)?)\s*(bps|kbps|Mbps|Gbps)', bitrate_str.strip())
            if not match:
                raise ValueError(f"Invalid bitrate format: {bitrate_str}")
            value = int(float(match.group(1)))
            unit_str = match.group(2)
            unit = BitrateUnit[unit_str]
            return DataValue(value=value, unit=unit)

        # Security configuration
        security = Security(
            k=subscriber.k,
            amf=subscriber.authenticationManagementField or "8000",
            op_type=0,  # OP type
            op_value=subscriber.opc,
            opc=subscriber.opc
        )

        ambr = AmbrData(
            downlink=DataValue(value=50, unit=BitrateUnit.Mbps),
            uplink=DataValue(value=50, unit=BitrateUnit.Mbps)
        )

        # Build slice configuration
        slices = []
        for idx, snssai in enumerate(subscriber.snssai):
            # Find matching slice profile
            slice_profile = None
            for sp in create5g_model.config.sliceProfiles:
                if sp.sliceId == snssai.sliceId and sp.sliceType == snssai.sliceType:
                    slice_profile = sp
                    break

            if not slice_profile:
                # Skip this slice if no profile found
                continue

            # Create sessions for each DNN in the slice
            sessions = []
            for dnn_name in slice_profile.dnnList:
                # Find DNN configuration
                dnn_config = create5g_model.get_dnn(dnn_name)

                if dnn_config:
                    # Use slice AMBR for session AMBR
                    session_ambr = AmbrData(
                        downlink=parse_bitrate(slice_profile.profileParams.sliceAmbr or "1000 Mbps"),
                        uplink=parse_bitrate(slice_profile.profileParams.sliceAmbr or "1000 Mbps")
                    )

                    session = Session(
                        name=dnn_config.dnn,
                        type=1,  # IPv4
                        ambr=session_ambr,
                        qos=Qos(
                            index=9,  # Default QoS index
                            arp=Arp(
                                priority_level=8,
                                pre_emption_capability=1,  # MAY_PREEMPT
                                pre_emption_vulnerability=1  # NOT_PREEMPTABLE
                            )
                        )
                    )
                    sessions.append(session)

            # Only add slice if it has sessions
            if sessions:
                subscriber_slice = SubscriberSlice(
                    sst=slice_profile.sliceType,
                    sd=slice_profile.sliceId if slice_profile.sliceId else None,
                    default_indicator=snssai.default_slice if snssai.default_slice is not None else (idx == 0),
                    session=sessions
                )
                slices.append(subscriber_slice)

        return cls(
            imsi=subscriber.imsi,
            security=security,
            ambr=ambr,
            subscriber_status=0,
            operator_determined_barring=0,
            slice=slices
        )

    def to_mongosh_insert(self) -> str:
        """Convert Open5gsSubscriber to MongoDB insertOne command string for mongosh"""

        def format_data_value(data_value: DataValue) -> str:
            """Format DataValue object as MongoDB object"""
            return f'{{ value: {data_value.value}, unit: {data_value.unit} }}'

        def format_ambr(ambr: AmbrData) -> str:
            """Format AmbrData object as MongoDB object"""
            return (
                f'{{ '
                f'downlink: {format_data_value(ambr.downlink)}, '
                f'uplink: {format_data_value(ambr.uplink)} '
                f'}}'
            )

        def format_arp(arp: Arp) -> str:
            """Format Arp object as MongoDB object"""
            return (
                f'{{ '
                f'priority_level: {arp.priority_level}, '
                f'pre_emption_capability: {arp.pre_emption_capability}, '
                f'pre_emption_vulnerability: {arp.pre_emption_vulnerability} '
                f'}}'
            )

        def format_qos(qos: Qos) -> str:
            """Format Qos object as MongoDB object"""
            return (
                f'{{ '
                f'index: {qos.index}, '
                f'arp: {format_arp(qos.arp)} '
                f'}}'
            )

        def format_session(session: Session) -> str:
            """Format Session object as MongoDB object"""
            return (
                f'{{ '
                f'name: "{session.name}", '
                f'type: {session.type}, '
                f'ambr: {format_ambr(session.ambr)}, '
                f'qos: {format_qos(session.qos)} '
                f'}}'
            )

        def format_slice(slice_item: SubscriberSlice) -> str:
            """Format SubscriberSlice object as MongoDB object"""
            sessions_str = ', '.join(format_session(s) for s in slice_item.session)
            sd_str = f'"{slice_item.sd}"' if slice_item.sd else 'null'
            return (
                f'{{ '
                f'sst: {slice_item.sst}, '
                f'sd: {sd_str}, '
                f'default_indicator: {str(slice_item.default_indicator).lower()}, '
                f'session: [{sessions_str}] '
                f'}}'
            )

        # Build the complete insertOne command
        slices_str = ', '.join(format_slice(s) for s in self.slice)

        mongo_script = (
            f'db.subscribers.insertOne({{ '
            f'imsi: "{self.imsi}", '
            f'security: {{ '
            f'k: "{self.security.k}", '
            f'amf: "{self.security.amf}", '
            f'op_type: {self.security.op_type}, '
            f'op_value: "{self.security.op_value}", '
            f'opc: "{self.security.opc}" '
            f'}}, '
            f'ambr: {format_ambr(self.ambr)}, '
            f'subscriber_status: {self.subscriber_status}, '
            f'operator_determined_barring: {self.operator_determined_barring}, '
            f'slice: [{slices_str}] '
            f'}})'
        )

        return mongo_script
