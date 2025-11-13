

from typing import Optional, Dict, Any, Literal, List

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.network.network_models import MultusInterface
from nfvcl_models.blueprint_ng.core5g.common import Create5gModel, MultusRoute
from nfvcl_models.blueprint_ng.g5.common5g import Slice5G


class OAIAreaModel(NFVCLBaseModel):
    id: int
    config: Optional[Dict[str, Any]] = Field(
        None,
        description='parameters for the day2 configurator of the Blueprint istance'
    )


class OAIBlueCreateModel(Create5gModel):
    type: Literal["OpenAirInterface"]


class SscModes(NFVCLBaseModel):
    defaultSscMode: str = Field(default='SSC_MODE_1', alias='defaultSscMode')


class SessionAmbr(NFVCLBaseModel):
    uplink: str = Field(default="1000Mbps")
    downlink: str = Field(default="1000Mbps")


class Arp(NFVCLBaseModel):
    preemptCap: str = Field(default="NOT_PREEMPT")
    preemptVuln: str = Field(default="NOT_PREEMPTABLE")
    priorityLevel: int = Field(default=15)


class FiveQosProfile(NFVCLBaseModel):
    five_qi: int = Field(alias='5qi')
    arp: Arp = Field(default=Arp())
    priorityLevel: int = Field(default=1)


class PduSessionTypes(NFVCLBaseModel):
    defaultSessionType: str = Field(default='IPV4', alias='defaultSessionType')


class DnnConfiguration(NFVCLBaseModel):
    ssc_mode: SscModes = Field(default=SscModes(), alias='sscModes')
    s_ambr: SessionAmbr = Field(alias='sessionAmbr')
    five_qosProfile: FiveQosProfile = Field(alias='5gQosProfile')
    pduSessionTypes: PduSessionTypes = Field(default=PduSessionTypes(), alias='pduSessionTypes')


class LogLevel(NFVCLBaseModel):
    general: str


class RegisterNf(NFVCLBaseModel):
    general: str


class Snssai(NFVCLBaseModel):
    sst: int
    sd: Optional[str] = Field(default="FFFFFF")


class Sbi(NFVCLBaseModel):
    port: int
    api_version: str
    interface_name: str


class OaiNfs(NFVCLBaseModel):
    host: str
    sbi: Sbi


class N2(NFVCLBaseModel):
    interface_name: str
    port: int


class Amf(OaiNfs):
    n2: N2


class N4(NFVCLBaseModel):
    interface_name: str
    port: int


class Smf(OaiNfs):
    n4: N4


class N3(NFVCLBaseModel):
    interface_name: str
    port: int


class N6(NFVCLBaseModel):
    interface_name: str


class N9(NFVCLBaseModel):
    interface_name: str
    port: int


class Upf(OaiNfs):
    n3: N3
    n4: N4
    n6: N6
    n9: N9


class CoreNfs(NFVCLBaseModel):
    amf: Amf
    smf: Smf
    upf: Upf
    lmf: OaiNfs = Field(alias='lmf')
    udm: OaiNfs = Field(alias='udm')
    udr: OaiNfs = Field(alias='udr')
    ausf: OaiNfs = Field(alias='ausf')
    nrf: OaiNfs = Field(alias='nrf')


class UpfNfs(NFVCLBaseModel):
    amf: Amf
    smf: Smf
    upf: Upf
    udm: OaiNfs = Field(alias='udm')
    udr: OaiNfs = Field(alias='udr')
    ausf: OaiNfs = Field(alias='ausf')
    nrf: OaiNfs = Field(alias='nrf')


class Database(NFVCLBaseModel):
    host: str
    user: str
    type: str
    password: str
    database_name: str
    generate_random: bool
    connection_timeout: int


class SupportFeaturesOptions(NFVCLBaseModel):
    enable_simple_scenario: str
    enable_nssf: str
    enable_smf_selection: str


class ServedGuamiListItem(NFVCLBaseModel):
    mcc: str
    mnc: str
    amf_region_id: str
    amf_set_id: str
    amf_pointer: str


class PlmnSupportListItem(NFVCLBaseModel):
    mcc: str
    mnc: str
    tac: int
    nssai: List[Snssai]


class AmfCore(NFVCLBaseModel):
    amf_name: str
    support_features_options: SupportFeaturesOptions
    relative_capacity: int
    statistics_timer_interval: int
    emergency_support: bool
    served_guami_list: List[ServedGuamiListItem]
    plmn_support_list: List[PlmnSupportListItem]
    supported_integrity_algorithms: List[str]
    supported_encryption_algorithms: List[str]


class SupportFeatures(NFVCLBaseModel):
    request_trp_info: str
    determine_num_gnb: str
    use_http2: str
    use_fqdn_dns: str
    register_nrf: str


class LmfCore(NFVCLBaseModel):
    http_threads_count: int
    gnb_id_bits_count: int
    num_gnb: int
    trp_info_wait_ms: int
    positioning_wait_ms: int
    measurement_wait_ms: int
    support_features: SupportFeatures


class SupportFeaturesSmf(NFVCLBaseModel):
    use_local_subscription_info: str
    use_local_pcc_rules: str


class Config(NFVCLBaseModel):
    enable_usage_reporting: str = Field(default="no")


class UpfAvailable(NFVCLBaseModel):
    host: str
    config: Config = Field(default_factory=Config)


class UeDns(NFVCLBaseModel):
    primary_ipv4: str
    primary_ipv6: str
    secondary_ipv4: str
    secondary_ipv6: str


class Ims(NFVCLBaseModel):
    pcscf_ipv4: str
    pcscf_ipv6: str


class DnnItem(NFVCLBaseModel):
    dnn: str


class SNssaiSmfInfoListItem(NFVCLBaseModel):
    sNssai: Snssai
    dnnSmfInfoList: List[DnnItem]


class SmfInfo(NFVCLBaseModel):
    sNssaiSmfInfoList: List[SNssaiSmfInfoListItem]


class QosProfile(NFVCLBaseModel):
    field_5qi: int = Field(alias='5qi')
    session_ambr_ul: str
    session_ambr_dl: str


class LocalSubscriptionInfo(NFVCLBaseModel):
    single_nssai: Snssai
    dnn: str
    qos_profile: QosProfile


class SmfCore(NFVCLBaseModel):
    ue_mtu: int
    support_features: SupportFeaturesSmf
    upfs: List[UpfAvailable]
    ue_dns: UeDns
    ims: Ims
    smf_info: SmfInfo
    local_subscription_infos: List[LocalSubscriptionInfo]


class SupportFeaturesUpf(NFVCLBaseModel):
    enable_bpf_datapath: str
    enable_snat: str
    enable_qos: str


class SNssaiUpfInfoListItem(NFVCLBaseModel):
    sNssai: Snssai
    dnnUpfInfoList: List[DnnItem]


class UpfInfo(NFVCLBaseModel):
    sNssaiUpfInfoList: List[SNssaiUpfInfoListItem]


class AvailableSmf(NFVCLBaseModel):
    host: str


class Upf2(NFVCLBaseModel):
    gnb_cidr: str
    support_features: SupportFeaturesUpf
    remote_n6_gw: str
    smfs: List[AvailableSmf]
    upf_info: UpfInfo


class Dnn(NFVCLBaseModel):
    dnn: str
    pdu_session_type: str = Field(default="IPV4")
    ipv4_subnet: str


class Baseconfig(NFVCLBaseModel):
    log_level: LogLevel
    register_nf: RegisterNf
    http_version: int
    snssais: List[Snssai]
    database: Database
    dnns: List[Dnn]


class Coreconfig(Baseconfig):
    nfs: CoreNfs
    curl_timeout: int
    amf: AmfCore
    smf: SmfCore
    lmf: LmfCore


class Upfconfig(Baseconfig):
    nfs: UpfNfs
    upf: Upf2


class Global(NFVCLBaseModel):
    kubernetesDistribution: str
    coreNetworkConfigMap: str
    clusterIpServiceIpAllocation: bool
    waitForNRF: bool
    waitForUDR: bool
    http2Param: str
    timeout: int
    coreconfig: Optional[Coreconfig] = Field(None, alias='currentconfig')


class Service(NFVCLBaseModel):
    annotations: Dict[str, Any]
    type: str
    port: int


class ImagePullSecret(NFVCLBaseModel):
    name: str


class Persistence(NFVCLBaseModel):
    enabled: bool
    storageClass: str


class Mysql(NFVCLBaseModel):
    enabled: bool
    imagePullPolicy: str
    oai5gdatabase: str
    imagePullSecrets: List[ImagePullSecret]
    persistence: Persistence


class Nfimage(NFVCLBaseModel):
    repository: str
    version: Optional[str] = Field(default=None)
    pullPolicy: str


class ConfigPod(NFVCLBaseModel):
    logLevel: str


class Persistent(NFVCLBaseModel):
    sharedvolume: bool
    storage_class: Optional[str] = Field(default=None, alias='storageClass')
    size: Optional[str] = Field(default=None)


class OaiNF(NFVCLBaseModel):
    enabled: bool
    nfimage: Nfimage
    include_tcp_dump_container: bool = Field(..., alias='includeTcpDumpContainer')
    persistent: Persistent
    image_pull_secrets: List[ImagePullSecret] = Field(..., alias='imagePullSecrets')
    config: ConfigPod
    node_selector: Dict[str, Any] = Field(..., alias='nodeSelector')


class Start(NFVCLBaseModel):
    tcpdump: bool


class StartNrf(Start):
    nrf: bool


class OaiNrf(OaiNF):
    start: StartNrf


class StartLmf(Start):
    lmf: bool


class OaiLmf(OaiNF):
    start: StartLmf


class StartUdr(Start):
    udr: bool


class OaiUdr(OaiNF):
    start: StartUdr


class StartUdm(Start):
    udm: bool


class OaiUdm(OaiNF):
    start: StartUdm


class SecurityContext(NFVCLBaseModel):
    privileged: bool


class StartAusf(Start):
    ausf: bool


class OaiAusf(OaiNF):
    start: StartAusf
    security_context: SecurityContext = Field(..., alias='securityContext')


class StartAmf(Start):
    amf: bool


class OaiAmf(OaiNF):
    start: StartAmf
    security_context: SecurityContext = Field(..., alias='securityContext')
    multus: Optional[OAIMultusAMF] = Field(default=None)


class StartSmf(Start):
    smf: bool

class SMFHostAliases(NFVCLBaseModel):
    ip: str = Field()
    hostnames: str = Field()

class OaiSmf(OaiNF):
    start: StartSmf
    hostAliases: List[SMFHostAliases]
    multus: Optional[OAIMultusSMF] = Field(default=None)


class OaiCoreValuesModel(NFVCLBaseModel):
    global_: Optional[Global] = Field(None, alias='global')
    mysql: Optional[Mysql] = None
    oai_nrf: Optional[OaiNrf] = Field(None, alias='oai-nrf')
    oai_lmf: Optional[OaiLmf] = Field(None, alias='oai-lmf')
    oai_udr: Optional[OaiUdr] = Field(None, alias='oai-udr')
    oai_udm: Optional[OaiUdm] = Field(None, alias='oai-udm')
    oai_ausf: Optional[OaiAusf] = Field(None, alias='oai-ausf')
    oai_amf: Optional[OaiAmf] = Field(None, alias='oai-amf')
    oai_smf: Optional[OaiSmf] = Field(None, alias='oai-smf')


class OAIMultusInterface(NFVCLBaseModel):
    create: bool
    ip_add: str = Field(..., alias='ipAdd')
    netmask: str
    name: Optional[str] = Field(default="")
    mac: Optional[str] = Field(default="")
    gateway: Optional[str] = Field(default="")
    routes: Optional[List[MultusRoute]] = Field(default_factory=list)
    host_interface: str = Field(alias='hostInterface')

    def set_multus(self, create: bool, multus_interface: MultusInterface, routes: Optional[List[MultusRoute]] = None):
        self.create = create
        self.ip_add = multus_interface.ip_address.exploded
        self.netmask = str(multus_interface.prefixlen)
        self.gateway = multus_interface.gateway_ip.exploded if multus_interface.gateway_ip else None
        self.routes = routes if routes else []
        self.host_interface = multus_interface.host_interface


class OAIMultusUPF(NFVCLBaseModel):
    defaultGateway: Optional[str] = Field(default=None)
    n3Interface: OAIMultusInterface
    n4Interface: OAIMultusInterface
    n6Interface: OAIMultusInterface


class OAIMultusAMF(NFVCLBaseModel):
    defaultGateway: Optional[str] = Field(default=None)
    n2Interface: OAIMultusInterface


class OAIMultusSMF(NFVCLBaseModel):
    defaultGateway: Optional[str] = Field(default=None)
    n4Interface: OAIMultusInterface


class OaiUpfValuesModel(NFVCLBaseModel):
    upfconfig: Optional[Upfconfig] = Field(None, alias='currentconfig')
    multus: OAIMultusUPF


# UE Model
class LastIndexes(NFVCLBaseModel):
    ausf: int = Field(default=0, alias='ausf')


class SequenceNumber(NFVCLBaseModel):
    sqn: str = Field(default="000000000020")
    sqn_scheme: str = Field(default="NON_TIME_BASED", alias='sqnScheme')
    last_indexes: LastIndexes = Field(default=LastIndexes(), alias='lastIndexes')


class Ue(NFVCLBaseModel):
    authentication_method: str = Field(default="5G_AKA", alias='authenticationMethod')
    enc_permanent_key: str = Field(alias='encPermanentKey')
    protection_parameter_id: str = Field(alias='protectionParameterId')
    sequence_number: SequenceNumber = Field(default=SequenceNumber(), alias='sequenceNumber')
    authentication_management_field: str = Field(
        default="8000", alias='authenticationManagementField'
    )
    algorithm_id: str = Field("milenage", alias='algorithmId')
    enc_opc_key: str = Field(alias='encOpcKey')
    enc_topc_key: str = Field(alias='encTopcKey')
    vector_generation_in_hss: bool = Field(default=False, alias='vectorGenerationInHss')
    n5gc_auth_method: str = Field(default="", alias='n5gcAuthMethod')
    rg_authentication_ind: bool = Field(default=False, alias='rgAuthenticationInd')
    supi: str


# SMS Model
class SessionManagementSubscriptionData(NFVCLBaseModel):
    dnn_configurations: Dict[str, DnnConfiguration] = Field(default={}, alias='dnnConfigurations')
    single_nssai: Snssai = Field(alias='singleNssai')
    ueid: Optional[str] = Field(default="", exclude=True)

    def add_configuration(self, dnn: str, configuration: DnnConfiguration):
        if (dnn, configuration) not in self.dnn_configurations.items():
            self.dnn_configurations[dnn] = configuration


class SessionsManagementSubscriptions(NFVCLBaseModel):
    sessions: List[SessionManagementSubscriptionData] = Field(default=[])


###################################################################################################
############################################### RAN ###############################################
###################################################################################################

############################################### CU ################################################
class ServiceAccount(NFVCLBaseModel):
    create: bool
    annotations: Dict[str, Any]
    name: str


class CUMultus(NFVCLBaseModel):
    default_gateway: str = Field(..., alias='defaultGateway')
    f1_interface: OAIMultusInterface = Field(..., alias='f1Interface')
    n2_interface: OAIMultusInterface = Field(..., alias='n2Interface')
    n3_interface: OAIMultusInterface = Field(..., alias='n3Interface')


class CUConfig(NFVCLBaseModel):
    time_zone: str = Field(..., alias='timeZone')
    use_additional_options: str = Field(..., alias='useAdditionalOptions')
    cu_name: str = Field(..., alias='cuName')
    mcc: str
    mnc: str
    tac: str
    snssai_list: List[Slice5G] = Field(alias='snssaiList')
    amfhost: str
    n2_if_name: str = Field(..., alias='n2IfName')
    n3_if_name: str = Field(..., alias='n3IfName')
    f1_if_name: str = Field(..., alias='f1IfName')
    f1cu_port: str = Field(..., alias='f1cuPort')
    f1du_port: str = Field(..., alias='f1duPort')
    gnb_id: str = Field(default="0xe00", alias='gnbId')
    additional_routes: Optional[List[str]] = Field(default=None, alias='additional_routes')


class PodSecurityContext(NFVCLBaseModel):
    run_as_user: int = Field(..., alias='runAsUser')
    run_as_group: int = Field(..., alias='runAsGroup')


class CUStart(NFVCLBaseModel):
    oaicu: bool
    tcpdump: bool


class Tcpdumpimage(NFVCLBaseModel):
    repository: str
    version: str
    pull_policy: str = Field(..., alias='pullPolicy')


class GenericRanPersistent(NFVCLBaseModel):
    sharedvolume: bool
    volume_name: str = Field(..., alias='volumeName')
    size: str


class Nf(NFVCLBaseModel):
    cpu: str
    memory: str


class Tcpdump(NFVCLBaseModel):
    cpu: str
    memory: str


class Limits(NFVCLBaseModel):
    nf: Nf
    tcpdump: Tcpdump


class Requests(NFVCLBaseModel):
    nf: Nf
    tcpdump: Tcpdump


class Resources(NFVCLBaseModel):
    define: bool
    limits: Limits
    requests: Requests


class CU(NFVCLBaseModel):
    multus: Optional[CUMultus] = None
    config: Optional[CUConfig] = None


############################################### CU-CP ##############################################

class CUCPMultus(NFVCLBaseModel):
    default_gateway: str = Field(..., alias='defaultGateway')
    e1_interface: OAIMultusInterface = Field(..., alias='e1Interface')
    n2_interface: OAIMultusInterface = Field(..., alias='n2Interface')
    f1c_interface: OAIMultusInterface = Field(..., alias='f1cInterface')


class CUCPConfig(NFVCLBaseModel):
    time_zone: str = Field(..., alias='timeZone')
    use_additional_options: str = Field(..., alias='useAdditionalOptions')
    cucp_name: str = Field(..., alias='cucpName')
    mcc: str
    mnc: str
    tac: str
    snssai_list: List[Slice5G] = Field(alias='snssaiList')
    amfhost: str
    n2_if_name: str = Field(..., alias='n2IfName')
    f1_if_name: str = Field(..., alias='f1IfName')
    e1_if_name: str = Field(..., alias='e1IfName')
    f1cu_port: str = Field(..., alias='f1cuPort')
    f1du_port: str = Field(..., alias='f1duPort')
    gnb_id: str = Field(default="0xe00", alias='gnbId')


class CUCPStart(NFVCLBaseModel):
    oaicucp: bool
    tcpdump: bool


class CUCP(NFVCLBaseModel):
    kubernetes_distribution: Optional[str] = Field(None, alias='kubernetesDistribution')
    nfimage: Optional[Nfimage] = None
    image_pull_secrets: Optional[List[ImagePullSecret]] = Field(None, alias='imagePullSecrets')
    service_account: Optional[ServiceAccount] = Field(None, alias='serviceAccount')
    multus: Optional[CUCPMultus] = None
    config: Optional[CUCPConfig] = None
    pod_security_context: Optional[PodSecurityContext] = Field(None, alias='podSecurityContext')
    security_context: Optional[SecurityContext] = Field(None, alias='securityContext')
    start: Optional[CUCPStart] = None
    include_tcp_dump_container: Optional[bool] = Field(None, alias='includeTcpDumpContainer')
    tcpdumpimage: Optional[Tcpdumpimage] = None
    persistent: Optional[GenericRanPersistent] = None
    resources: Optional[Resources] = None
    tolerations: Optional[List] = None
    affinity: Optional[Dict[str, Any]] = None
    termination_grace_period_seconds: Optional[int] = Field(None, alias='terminationGracePeriodSeconds')
    node_selector: Optional[Dict[str, Any]] = Field(None, alias='nodeSelector')
    node_name: Optional[Any] = Field(None, alias='nodeName')


############################################### CU-UP ##############################################

class CUUPMultus(NFVCLBaseModel):
    default_gateway: str = Field(..., alias='defaultGateway')
    e1_interface: OAIMultusInterface = Field(..., alias='e1Interface')
    n3_interface: OAIMultusInterface = Field(..., alias='n3Interface')
    f1u_interface: OAIMultusInterface = Field(..., alias='f1uInterface')


class CUUPConfig(NFVCLBaseModel):
    time_zone: str = Field(..., alias='timeZone')
    use_additional_options: str = Field(..., alias='useAdditionalOptions')
    cuup_name: str = Field(..., alias='cuupName')
    mcc: str
    mnc: str
    tac: str
    snssai_list: List[Slice5G] = Field(alias='snssaiList')
    flexrichost: str
    cu_cp_host: str = Field(..., alias='cuCpHost')
    n2_if_name: str = Field(..., alias='n2IfName')
    n3_if_name: str = Field(..., alias='n3IfName')
    f1_if_name: str = Field(..., alias='f1IfName')
    e1_if_name: str = Field(..., alias='e1IfName')
    f1cu_port: str = Field(..., alias='f1cuPort')
    f1du_port: str = Field(..., alias='f1duPort')
    gnb_id: str = Field(default="0xe00", alias='gnbId')
    additional_routes: Optional[List[str]] = Field(default=None, alias='additional_routes')


class CUUPStart(NFVCLBaseModel):
    oaicuup: bool
    tcpdump: bool


class CUUP(NFVCLBaseModel):
    kubernetes_distribution: Optional[str] = Field(None, alias='kubernetesDistribution')
    nfimage: Optional[Nfimage] = None
    image_pull_secrets: Optional[List[ImagePullSecret]] = Field(None, alias='imagePullSecrets')
    service_account: Optional[ServiceAccount] = Field(None, alias='serviceAccount')
    multus: Optional[CUUPMultus] = None
    config: Optional[CUUPConfig] = None
    pod_security_context: Optional[PodSecurityContext] = Field(None, alias='podSecurityContext')
    security_context: Optional[SecurityContext] = Field(None, alias='securityContext')
    start: Optional[CUUPStart] = None
    include_tcp_dump_container: Optional[bool] = Field(None, alias='includeTcpDumpContainer')
    tcpdumpimage: Optional[Tcpdumpimage] = None
    persistent: Optional[GenericRanPersistent] = None
    resources: Optional[Resources] = None
    tolerations: Optional[List] = None
    affinity: Optional[Dict[str, Any]] = None
    termination_grace_period_seconds: Optional[int] = Field(None, alias='terminationGracePeriodSeconds')
    node_selector: Optional[Dict[str, Any]] = Field(None, alias='nodeSelector')
    node_name: Optional[Any] = Field(None, alias='nodeName')


############################################### DU ##############################################

class DUMultus(NFVCLBaseModel):
    default_gateway: str = Field(..., alias='defaultGateway')
    f1_interface: OAIMultusInterface = Field(..., alias='f1Interface')
    ru1_interface: OAIMultusInterface = Field(..., alias='ru1Interface')
    ru2_interface: OAIMultusInterface = Field(..., alias='ru2Interface')


class DUConfig(NFVCLBaseModel):
    time_zone: str = Field(..., alias='timeZone')
    use_additional_options: str = Field(..., alias='useAdditionalOptions')
    du_name: str = Field(..., alias='duName')
    mcc: str
    mnc: str
    tac: str
    snssai_list: List[Slice5G] = Field(alias='snssaiList')
    usrp: str
    f1_if_name: str = Field(..., alias='f1IfName')
    cu_host: str = Field(..., alias='cuHost')
    f1cu_port: str = Field(..., alias='f1cuPort')
    f1du_port: str = Field(..., alias='f1duPort')
    gnb_id: str = Field(default="0xe00", alias='gnbId')


class DUStart(NFVCLBaseModel):
    gnbdu: bool
    tcpdump: bool


class DU(NFVCLBaseModel):
    multus: Optional[DUMultus] = None
    config: Optional[DUConfig] = None


############################################### GNB ##############################################


class GNBMultus(NFVCLBaseModel):
    default_gateway: str = Field(..., alias='defaultGateway')
    n2_interface: OAIMultusInterface = Field(..., alias='n2Interface')
    n3_interface: OAIMultusInterface = Field(..., alias='n3Interface')
    ru1_interface: OAIMultusInterface = Field(..., alias='ru1Interface')
    ru2_interface: OAIMultusInterface = Field(..., alias='ru2Interface')


class GNBConfig(NFVCLBaseModel):
    time_zone: str = Field(..., alias='timeZone')
    use_additional_options: str = Field(..., alias='useAdditionalOptions')
    gnb_name: str = Field(..., alias='gnbName')
    mcc: str
    mnc: str
    tac: str
    snssai_list: List[Slice5G] = Field(alias='snssaiList')
    usrp: str
    n2_if_name: str = Field(default="eth0", alias='n2IfName')
    n3_if_name: str = Field(default="eth0", alias='n3IfName')
    amf_ip_address: str = Field(..., alias='amfIpAddress')
    gnb_id: str = Field(default="0xe00", alias='gnbId')
    additional_routes: Optional[List[str]] = Field(default=None, alias='additional_routes')


class GNBStart(NFVCLBaseModel):
    gnb: bool
    tcpdump: bool


class GNB(NFVCLBaseModel):
    multus: Optional[GNBMultus] = None
    config: Optional[GNBConfig] = None


############################################### UE ##############################################

class OAIUEConfig(NFVCLBaseModel):
    time_zone: str = Field(..., alias='timeZone')
    rf_sim_server: str = Field(..., alias='rfSimServer')
    full_imsi: str = Field(..., alias='fullImsi')
    full_key: str = Field(..., alias='fullKey')
    opc: str
    dnn: str
    sst: str
    sd: str  # HEX is allowed?
    usrp: str
    use_additional_options: str = Field(..., alias='useAdditionalOptions')


class OAIUE(NFVCLBaseModel):
    multus: Optional[OAIMultusInterface] = None
    config: Optional[OAIUEConfig] = None
