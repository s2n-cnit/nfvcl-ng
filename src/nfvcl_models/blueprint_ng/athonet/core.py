

from typing import List, Optional, Dict, Any

from pydantic import Field, RootModel

from nfvcl_models.blueprint_ng.athonet.upf import DnnVrf
from nfvcl_models.blueprint_ng.core5g.common import Create5gModel, SubSliceProfiles, SubDataNets
from nfvcl_models.blueprint_ng.g5.core import Core5GAddSubscriberModel
from nfvcl_common.base_model import NFVCLBaseModel


#################### ATHONET ACCESS TOKEN ####################


class AthonetAccessToken(NFVCLBaseModel):
    access_token: str
    refresh_token: str


#################### PROVISIONED DATA INFO ####################

class ProvisionedDataInfo(NFVCLBaseModel):
    slice: SubSliceProfiles
    dnn: SubDataNets


#################### AMF APPLICATION CONFIG ####################

class Nameserver(NFVCLBaseModel):
    remote_addr: str
    remote_port: int


class Dns(NFVCLBaseModel):
    local_addr: str
    nameservers: List[Nameserver]
    retry: int
    usevc: bool
    edns: bool
    udp_payload_size: int
    dev: str
    timeout_ms: int
    query_type: str
    cache_ttl_ms: int


class NfProfile(NFVCLBaseModel):
    locality: str
    nf_instance_name: str
    nrf_suggested_heartbeat: int
    nrf_api_root: str


class SbiTransport(NFVCLBaseModel):
    name: str
    local_addr: str
    dev: str
    local_port: int


class Sbi(NFVCLBaseModel):
    dns: Dns
    nf_profile: NfProfile
    transports: List[SbiTransport]


class Logs(NFVCLBaseModel):
    level: str


class License(NFVCLBaseModel):
    license_server: str
    license_id: str


class PlmnId(NFVCLBaseModel):
    mcc: str
    mnc: str


class SNssaiListItem(NFVCLBaseModel):
    sd: str
    sst: int


class PerPlmnSnssaiListItem(NFVCLBaseModel):
    plmn_id: PlmnId
    s_nssai_list: List[SNssaiListItem] = Field(default_factory=list)


class Timers(NFVCLBaseModel):
    t3512: int
    t3513: int
    t3522: int
    t3550: int
    t3555: int
    t3560: int
    t3570: int
    tImplicitDetach: int
    tMobileReachable: int
    tPurge: int


class Security(NFVCLBaseModel):
    encryption_algorithms: List[str]
    integrity_algorithms: List[str]


class Nas5gs(NFVCLBaseModel):
    timers: Timers
    security: Security


class Eir(NFVCLBaseModel):
    validity_check_timeout_ms: int
    check_enabled: bool
    eir_fail_allowed: bool
    equipment_unknown_allowed: bool
    exonerated_plmns: List
    greylist_allowed: bool


class Acl(NFVCLBaseModel):
    default: str
    rules: List


class MmInfo(NFVCLBaseModel):
    full_network_name: str
    short_network_name: str


class GuamiListItem(NFVCLBaseModel):
    plmn_id: PlmnId
    amf_id: str


class Settings(NFVCLBaseModel):
    amf_name: str
    amf_relative_capacity: int


class TransportConfig(NFVCLBaseModel):
    tos: int
    dev: str
    local_port: int
    local_addrs: List[str]


class N2ITransport(NFVCLBaseModel):
    name: str
    transport_config: TransportConfig


class N2Interface(NFVCLBaseModel):
    settings: Settings
    transports: List[N2ITransport]


class AthonetApplicationAmfConfig(NFVCLBaseModel):
    sbi: Optional[Sbi] = None
    logs: Optional[Logs] = None
    api_version: Optional[str] = None
    amf_set_id: Optional[str] = None
    license: Optional[License] = None
    per_plmn_snssai_list: Optional[List[PerPlmnSnssaiListItem]] = None
    nas_5gs: Optional[Nas5gs] = None
    eir: Optional[Eir] = None
    acl: Optional[Acl] = None
    mm_info: Optional[MmInfo] = None
    guami_list: Optional[List[GuamiListItem]] = None
    amf_region_id: Optional[str] = None
    n2_interface: Optional[N2Interface] = None

    def configure(self, config: Create5gModel):
        """
        Configure AMF according to core payload model
        Args:
            config: core model

        """
        self.per_plmn_snssai_list.clear()
        self.guami_list.clear()
        mcc = config.config.plmn[0:3]
        mnc = config.config.plmn[-2:]

        plmn_snssai_item = PerPlmnSnssaiListItem(
            plmn_id=PlmnId(mcc=mcc, mnc=mnc)
        )

        for area in config.areas:
            for _slice in area.slices:
                item = SNssaiListItem(
                    sst=_slice.sliceType,
                    sd=_slice.sliceId
                )
                plmn_snssai_item.s_nssai_list.append(item)

        self.per_plmn_snssai_list.append(plmn_snssai_item)

        guami_list_item = GuamiListItem(
            plmn_id=PlmnId(mcc=mcc, mnc=mnc),
            amf_id="000001"
        )
        self.guami_list.append(guami_list_item)


#################### AUSF APPLICATION CONFIG ####################

class AthonetApplicationAusfConfig(NFVCLBaseModel):
    sbi: Optional[Sbi] = None
    logs: Optional[Logs] = None
    license: Optional[License] = None


#################### CHF APPLICATION CONFIG ####################

class Ftp(NFVCLBaseModel):
    enabled: bool
    name: str
    type: str
    tos: int
    user: str
    local_addr: str
    password: str
    local_port: int


class Gtpprime(NFVCLBaseModel):
    transports: List


class Sftp(NFVCLBaseModel):
    enabled: bool
    name: str
    type: str
    tos: int
    user: str
    local_addr: str
    password: str
    local_port: int


class Storage(NFVCLBaseModel):
    age_limit_ms: int
    records_limit_count: int
    size_limit_bytes: int
    expire_days: int
    node_id: str
    node_ip: str
    storage_path: str
    storage_pattern: str
    storage_work_dir: str


class SessionOptions(NFVCLBaseModel):
    timeout_ms: int


class AthonetApplicationChfConfig(NFVCLBaseModel):
    ftp: Optional[Ftp] = None
    gtpprime: Optional[Gtpprime] = None
    sbi: Optional[Sbi] = None
    sftp: Optional[Sftp] = None
    storage: Optional[Storage] = None
    logs: Optional[Logs] = None
    license: Optional[License] = None
    session_options: Optional[SessionOptions] = None


#################### DNS APPLICATION CONFIG ####################


class AllowQueryItem(NFVCLBaseModel):
    type: str
    value: str


class AllowQueryCacheItem(NFVCLBaseModel):
    type: str
    value: str


class AllowQueryOnItem(NFVCLBaseModel):
    type: str
    value: str


class Element(NFVCLBaseModel):
    type: str
    value: str


class ListenOnItem(NFVCLBaseModel):
    elements: List[Element]


class DnsOptions(NFVCLBaseModel):
    notify: str
    allow_query: List[AllowQueryItem]
    allow_query_cache: List[AllowQueryCacheItem]
    allow_query_on: List[AllowQueryOnItem]
    listen_on: List[ListenOnItem]


class Zone(NFVCLBaseModel):
    name: str
    notify: str
    type: str


class Named(NFVCLBaseModel):
    options: DnsOptions
    server: str
    vrf: str
    zones: List[Zone]


class AthonetApplicationDnsConfig(NFVCLBaseModel):
    logs: Optional[Logs] = None
    api_version: Optional[str] = None
    nameds: Optional[List[Named]] = None


#################### NRF APPLICATION CONFIG ####################


class NrfTransport(NFVCLBaseModel):
    name: str
    local_addr: str
    dev: str
    local_port: int


class NrfSbi(NFVCLBaseModel):
    nf_profile: NfProfile
    transports: List[NrfTransport]


class ValidityTimer(NFVCLBaseModel):
    default: int


class Subscription(NFVCLBaseModel):
    validity_timer: ValidityTimer


class HeartBeatTimer(NFVCLBaseModel):
    default: int
    maximum: int
    minimum: int


class NfProfiles(NFVCLBaseModel):
    heart_beat_timer: HeartBeatTimer


class App(NFVCLBaseModel):
    subscription: Subscription
    nf_profiles: NfProfiles


class AthonetApplicationNrfConfig(NFVCLBaseModel):
    sbi: Optional[NrfSbi] = None
    app: Optional[App] = None
    logs: Optional[Logs] = None
    api_version: Optional[str] = None
    license: Optional[License] = None


#################### PCF APPLICATION CONFIG ####################

class PcfOptions(NFVCLBaseModel):
    restrict_connections: bool
    allow_only_connections_from_static_peers: bool


class Capabilities(NFVCLBaseModel):
    vendor_id: int
    origin_host: str
    origin_realm: str
    product_name: str


class PcfTransportConfig(NFVCLBaseModel):
    tos: int
    recbuf: int
    sndbuf: int
    dev: str
    config_type: str
    local_addrs: Optional[List[str]] = None
    local_port: int
    max_concurrent_outgoing_req: int
    local_addr: Optional[str] = None


class PcfStackTransport(NFVCLBaseModel):
    name: str
    transport_config: PcfTransportConfig


class Action(NFVCLBaseModel):
    action_type: str
    direct_delivery: bool
    timeout_ms: int


class Selectors(NFVCLBaseModel):
    selector_type: str


class Route(NFVCLBaseModel):
    name: str
    action: Action
    selectors: Selectors


class Stack(NFVCLBaseModel):
    name: str
    options: PcfOptions
    applications: List[str]
    capabilities: Capabilities
    transports: List[PcfStackTransport]
    target_tables: List
    routes: List[Route]
    static_peers: List


class Diameter(NFVCLBaseModel):
    stacks: List[Stack]


class Emergency(NFVCLBaseModel):
    service: str
    dnns: List[str]
    service_urns: List[str]


class Script(NFVCLBaseModel):
    id: str
    base64: str


class Sm(NFVCLBaseModel):
    scripts: List[Script]


class Am(NFVCLBaseModel):
    scripts: List


class PcfApp(NFVCLBaseModel):
    emergency: Emergency
    sm: Sm
    am: Am
    n5_session_timeout_ms: int


class AthonetApplicationPcfConfig(NFVCLBaseModel):
    diameter: Optional[Diameter] = None
    sbi: Optional[Sbi] = None
    app: Optional[PcfApp] = None
    logs: Optional[Logs] = None
    api_version: Optional[str] = None
    license: Optional[License] = None


#################### SMF APPLICATION CONFIG ####################

class SmfTransportConfig(NFVCLBaseModel):
    type: str
    local_addr: str
    dev: str


class Transport(NFVCLBaseModel):
    name: str
    transport_config: SmfTransportConfig


class Gtpu(NFVCLBaseModel):
    transports: List[Transport]


class PfcpTransportConfig(NFVCLBaseModel):
    type: str
    tos: Optional[int] = Field(None)
    local_addr: str
    dev: str


class PfcpTransport(NFVCLBaseModel):
    name: str
    transport_config: PfcpTransportConfig


class Pfcp(NFVCLBaseModel):
    transports: List[PfcpTransport]


class SmfTransport(NFVCLBaseModel):
    name: str
    local_addr: str
    dev: str
    local_port: int


class SmfSbi(NFVCLBaseModel):
    dns: Dns
    transports: List[SmfTransport]
    nf_profile: NfProfile


class DownlinkItem(NFVCLBaseModel):
    dscp: int
    field_5qi: int = Field(..., alias='5qi')


class DscpMapping(NFVCLBaseModel):
    downlink: List[DownlinkItem]


class AdditionalIes(NFVCLBaseModel):
    s_nssai: bool
    apn_dnn: bool
    user_id: bool


class NetworkInstances(NFVCLBaseModel):
    n3: str
    n4_u: str
    s5s8_u: str


class UpfOptions(NFVCLBaseModel):
    fteid_allocation: str
    dscp_mapping: DscpMapping
    additional_ies: AdditionalIes
    network_instances: NetworkInstances


class Default(NFVCLBaseModel):
    active: bool
    measurement_period_sec: int


class Charging(NFVCLBaseModel):
    default: Default
    characteristics: List


class SNssai(NFVCLBaseModel):
    sst: int
    sd: Optional[str] = None


class SmfDns(NFVCLBaseModel):
    ipv4_addrs: List[str]
    ipv6_addrs: List = Field(default_factory=list)


class Pcscf(NFVCLBaseModel):
    ipv4_addrs: List = Field(default_factory=list)
    ipv6_addrs: List = Field(default_factory=list)


class IpAllocation(NFVCLBaseModel):
    allocator: str = Field(default="UPF_POOL")
    dns: SmfDns
    pcscf: Pcscf = Field(default_factory=Pcscf)


class Dnn(NFVCLBaseModel):
    dnn: str
    s_nssai: SNssai
    ip_allocation: IpAllocation


class StackConfig(NFVCLBaseModel):
    echo_interval_ms: int
    max_retransmissions: int
    retransmission_timeout_ms: int


class StackTransportConfig(NFVCLBaseModel):
    type: str
    tos: Optional[int] = Field(default=None)
    local_addr: str
    dev: str
    whitelist: List[str]


class SmfStackTransport(NFVCLBaseModel):
    name: str
    transport_config: StackTransportConfig


class SmfStack(NFVCLBaseModel):
    name: str
    stack_config: StackConfig
    transports: List[SmfStackTransport]


class Gtpc(NFVCLBaseModel):
    stacks: List[SmfStack]


class Upf(NFVCLBaseModel):
    name: str = Field(default="UPF_1")
    ip: str
    network_instance: str


class UpfProfile(NFVCLBaseModel):
    dnn: str
    s_nssai: SNssai
    upfs: List[Upf]


class AthonetApplicationSmfConfig(NFVCLBaseModel):
    gtpu: Optional[Gtpu] = None
    pfcp: Optional[Pfcp] = None
    sbi: Optional[SmfSbi] = None
    logs: Optional[Logs] = None
    api_version: Optional[str] = None
    license: Optional[License] = None
    upf_options: Optional[UpfOptions] = None
    charging: Optional[Charging] = None
    dnns: Optional[List[Dnn]] = None
    gtpc: Optional[Gtpc] = None
    upf_profiles: Optional[List[UpfProfile]] = None

    def configure(self, dnn_vrf: List[DnnVrf], upf_ip: str, config: Create5gModel):
        """
        Configure SMF according to core payload model
        Args:
            upf_ip: ip of upf to communicate with
            dnn_vrf: list of all available dnn with associated cidr and dns
            config: core model

        """
        self.dnns.clear()
        self.upf_profiles.clear()

        for _slice in config.config.sliceProfiles:
            for dnn in config.config.network_endpoints.data_nets:
                if _slice.dnnList[0] == dnn.dnn:
                    for supported_dnn in dnn_vrf:
                        if supported_dnn.cidr == dnn.pools[0].cidr:
                            dnn_item = Dnn(
                                dnn=dnn.dnn,
                                s_nssai=SNssai(
                                    sst=_slice.sliceType,
                                    sd=_slice.sliceId
                                ),
                                ip_allocation=IpAllocation(
                                    dns=SmfDns(
                                        ipv4_addrs=[supported_dnn.dns]
                                    )
                                )
                            )
                            self.dnns.append(dnn_item)

                            upf_item = UpfProfile(
                                dnn=dnn.dnn,
                                s_nssai=SNssai(
                                    sst=_slice.sliceType,
                                    sd=_slice.sliceId
                                ),
                                upfs=[
                                    Upf(
                                        ip=upf_ip,
                                        network_instance=f"NI_{supported_dnn.vrf}"
                                    )
                                ]
                            )
                            self.upf_profiles.append(upf_item)


#################### UDM APPLICATION CONFIG ####################

class UdmOptions(NFVCLBaseModel):
    restrict_connections: bool
    allow_only_connections_from_static_peers: bool


class UdmTransportConfig(NFVCLBaseModel):
    tos: int
    recbuf: int
    sndbuf: int
    dev: str
    config_type: str
    local_port: int
    max_concurrent_outgoing_req: int
    local_addrs: Optional[List[str]] = None
    local_addr: Optional[str] = None


class UdmStackTransport(NFVCLBaseModel):
    name: str
    transport_config: UdmTransportConfig


class UdmStack(NFVCLBaseModel):
    name: str
    options: UdmOptions
    applications: List[str]
    capabilities: Capabilities
    transports: List[UdmStackTransport]
    target_tables: List
    routes: List[Route]
    static_peers: List


class UdmDiameter(NFVCLBaseModel):
    version: str
    stacks: List[UdmStack]


class UdmSbiTransport(NFVCLBaseModel):
    name: str
    local_addr: str
    dev: str
    local_port: int


class UdmSbi(NFVCLBaseModel):
    dns: Dns
    transports: List[UdmSbiTransport]
    nf_profile: NfProfile


class DiameterInterface(NFVCLBaseModel):
    application: str
    stack: str


class Hplmn(NFVCLBaseModel):
    mcc: str
    mnc: str


class AthonetApplicationUdmConfig(NFVCLBaseModel):
    diameter: Optional[UdmDiameter] = None
    sbi: Optional[UdmSbi] = None
    logs: Optional[Logs] = None
    license: Optional[License] = None
    diameter_interfaces: Optional[List[DiameterInterface]] = None
    hplmns: Optional[List[Hplmn]] = None

    def configure(self, config: Create5gModel):
        """
        Configure UDM according to core payload model
        Args:
            config: core model

        """
        self.hplmns.clear()
        hplmn = Hplmn(mcc=config.config.plmn[0:3], mnc=config.config.plmn[-2:])
        self.hplmns.append(hplmn)


#################### UDR APPLICATION CONFIG ####################


class UdrTransport(NFVCLBaseModel):
    name: str
    local_addr: str
    dev: str
    local_port: int


class UdrSbi(NFVCLBaseModel):
    dns: Dns
    nf_profile: NfProfile
    transports: List[UdrTransport]


class AthonetApplicationUdrConfig(NFVCLBaseModel):
    sbi: Optional[UdrSbi] = None
    logs: Optional[Logs] = None
    license: Optional[License] = None


#################### CORE APPLICATION CONFIG #####################

class AthonetApplicationCoreConfig(NFVCLBaseModel):
    amf: Optional[AthonetApplicationAmfConfig] = Field(None)
    ausf: Optional[AthonetApplicationAusfConfig] = Field(None)
    chf: Optional[AthonetApplicationChfConfig] = Field(None)
    dns: Optional[AthonetApplicationDnsConfig] = Field(None)
    pcf: Optional[AthonetApplicationPcfConfig] = Field(None)
    nrf: Optional[AthonetApplicationNrfConfig] = Field(None)
    smf: Optional[AthonetApplicationSmfConfig] = Field(None)
    udm: Optional[AthonetApplicationUdmConfig] = Field(None)
    udr: Optional[AthonetApplicationUdrConfig] = Field(None)


#################### PROVISIONED DATA PROFILE #####################

class DefaultSingleNssai(NFVCLBaseModel):
    sd: str
    sst: int


class SingleNssai(NFVCLBaseModel):
    sd: str
    sst: int


class Nssai(NFVCLBaseModel):
    default_single_nssais: List[DefaultSingleNssai] = Field(
        default_factory=list, alias='defaultSingleNssais'
    )
    single_nssais: List[SingleNssai] = Field(default_factory=list, alias='singleNssais')


class SubscribedUeAmbr(NFVCLBaseModel):
    downlink: str = Field(default="1 Gbps")
    uplink: str = Field(default="1 Gbps")


class AmData(NFVCLBaseModel):
    nssai: Nssai = Field(default_factory=Nssai)
    subscribed_ue_ambr: SubscribedUeAmbr = Field(default_factory=SubscribedUeAmbr, alias='subscribedUeAmbr')


class PduSessionTypes(NFVCLBaseModel):
    default_session_type: str = Field(default="IPV4", alias='defaultSessionType')


class SscModes(NFVCLBaseModel):
    default_ssc_mode: str = Field(default="SSC_MODE_1", alias='defaultSscMode')


class SessionAmbr(NFVCLBaseModel):
    downlink: str = Field(default="1 Gbps")
    uplink: str = Field(default="1 Gbps")


class Arp(NFVCLBaseModel):
    preempt_cap: str = Field(..., alias='preemptCap')
    preempt_vuln: str = Field(..., alias='preemptVuln')
    priority_level: int = Field(..., alias='priorityLevel')


class Field5gQosProfile(NFVCLBaseModel):
    arp: Arp
    field_5qi: int = Field(..., alias='5qi')


class DnnConfiguration(NFVCLBaseModel):
    pdu_session_types: PduSessionTypes = Field(default_factory=PduSessionTypes, alias='pduSessionTypes')
    ssc_modes: SscModes = Field(default_factory=SscModes, alias='sscModes')
    session_ambr: SessionAmbr = Field(default_factory=SessionAmbr, alias='sessionAmbr')
    # field_5g_qos_profile: Field5gQosProfile = Field(..., alias='5gQosProfile')


class DnnConfigurations(RootModel):
    root: Dict[str, DnnConfiguration]


class SmDatum(NFVCLBaseModel):
    single_nssai: SingleNssai = Field(..., alias='singleNssai')
    dnn_configurations: DnnConfigurations = Field(alias='dnnConfigurations')


class DnnInfo(NFVCLBaseModel):
    default_dnn_indicator: bool = Field(False, alias='defaultDnnIndicator')
    dnn: str


class SliceField(NFVCLBaseModel):
    dnn_infos: List[DnnInfo] = Field(..., alias='dnnInfos')


class SubscribedSnssaiInfos(RootModel):
    root: Dict[str, SliceField] = Field(default_factory=dict)


class SmfSelData(NFVCLBaseModel):
    subscribed_snssai_infos: SubscribedSnssaiInfos = Field(
        default_factory=SubscribedSnssaiInfos, alias='subscribedSnssaiInfos'
    )


class SmsSubsData(NFVCLBaseModel):
    sms_subscribed: bool = Field(False, alias='smsSubscribed')


class SmsMngData(NFVCLBaseModel):
    mo_sms_subscribed: bool = Field(False, alias='moSmsSubscribed')
    mt_sms_subscribed: bool = Field(False, alias='mtSmsSubscribed')


class Data(NFVCLBaseModel):
    am_data: AmData = Field(default_factory=AmData, alias='amData')
    sm_data: List[SmDatum] = Field(default_factory=list, alias='smData')
    smf_sel_data: SmfSelData = Field(default_factory=SmfSelData, alias='smfSelData')
    sms_subs_data: SmsSubsData = Field(default_factory=SmsSubsData, alias='smsSubsData')
    sms_mng_data: SmsMngData = Field(default_factory=SmsMngData, alias='smsMngData')


class PlmnRule(NFVCLBaseModel):
    data: Data = Field(default_factory=Data, alias='data')
    action: str = Field(default="DATA")


class PlmnRulesMap(RootModel):
    root: Dict[str, PlmnRule]


class ProvisionedDataProfile(NFVCLBaseModel):
    description: Optional[str] = None
    plmn_rules_map: Optional[PlmnRulesMap] = None

    def configure(self, subscriber_model: Core5GAddSubscriberModel, add_infos: List[ProvisionedDataInfo]):
        """
        Configure ProvisionedDataProfile according to subscriber_model and add_infos
        Args:
            subscriber_model: subscriber info
            add_infos: list of user's slices associated with their dnns

        """
        self.description = subscriber_model.imsi
        plmn_rule = PlmnRule()
        data = Data()
        datums: List[SmDatum] = []
        for user_slice in subscriber_model.snssai:
            for info in add_infos:
                if info.slice.sliceId == user_slice.sliceId:
                    if len(data.am_data.nssai.default_single_nssais) == 0:
                        data.am_data.nssai.default_single_nssais.append(
                            DefaultSingleNssai(
                                sd=info.slice.sliceId,
                                sst=info.slice.sliceType,
                            )
                        )
                    data.am_data.nssai.single_nssais.append(
                        SingleNssai(
                            sd=info.slice.sliceId,
                            sst=info.slice.sliceType
                        )
                    )

                    datum = SmDatum(
                        single_nssai=SingleNssai(
                            sd=info.slice.sliceId,
                            sst=info.slice.sliceType
                        ),
                        dnn_configurations=DnnConfigurations.model_validate({f"{info.dnn.dnn}": DnnConfiguration()})
                    )
                    datums.append(datum)

                    smf_sel_data = SmfSelData()
                    smf_sel_data.subscribed_snssai_infos.root[f"{info.slice.sliceType}-{info.slice.sliceId}"] = SliceField(
                        dnn_infos=[DnnInfo(
                            dnn=info.dnn.dnn
                        )]
                    )
                    data.smf_sel_data = smf_sel_data

        data.sm_data = datums
        plmn_rule.data = data
        self.plmn_rules_map = PlmnRulesMap.model_validate({"*": PlmnRule(data=data)})


#################### SUPI DATA #####################

class UserProvisionedDataProfile(NFVCLBaseModel):
    uuid: str
    patches: List = Field(default_factory=list)


class AuthenticationSubscription(NFVCLBaseModel):
    k: str
    opc: str


class Supi(NFVCLBaseModel):
    supi: str
    description: Optional[str] = None
    status: str = Field(default="ACTIVE")
    provisioned_data_profile: UserProvisionedDataProfile
    authentication_subscription: AuthenticationSubscription


class AvailableSupisAuthenticationSubscription(NFVCLBaseModel):
    modified_at: str
    created_at: str
    auth_method: str
    k_provisioned: bool
    opc_provisioned: bool


class AvailableSupisDatum(NFVCLBaseModel):
    status: str
    description: Optional[str]
    gpsi: Any
    supi: str
    modified_at: str
    created_at: str
    provisioned_data_profile: UserProvisionedDataProfile
    authentication_subscription: AvailableSupisAuthenticationSubscription


class AvailableSupis(NFVCLBaseModel):
    data: List[AvailableSupisDatum]
    metadata: Metadata


#################### AVAILABLE PLMNS #####################

class PlmnsDatum(NFVCLBaseModel):
    mcc: str
    mnc: str
    modified_at: str
    created_at: str

    def __eq__(self, other: Any) -> bool:
        return self.mcc == other.mcc and self.mnc == other.mnc


class Metadata(NFVCLBaseModel):
    next_token: Any
    prev_token: Any


class Plmns(NFVCLBaseModel):
    data: List[PlmnsDatum]
    metadata: Metadata
