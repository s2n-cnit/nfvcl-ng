from typing import *

from pydantic import Field

from nfvcl.blueprints.blue_5g_base.blueprint_5g_base_beta import Blueprint5GBaseModel
from nfvcl.blueprints.blue_5g_base.models import Create5gModel
from nfvcl.blueprints.blue_5g_base.models.blue_5g_model import SubSubscribers, SubSliceProfiles, SubArea
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.k8s.k8s_objects import K8sService


class OAIAreaModel(NFVCLBaseModel):
    id: int
    config: Optional[Dict[str, Any]] = Field(
        None,
        description='parameters for the day2 configurator of the Blueprint istance'
    )


class OAIBlueCreateModel(Create5gModel):
    type: Literal["OpenAirInterface"]


class OAIAddSubscriberModel(SubSubscribers):
    type: Literal["OpenAirInterface"] = Field(default="OpenAirInterface")
    operation: Literal["add_ues"] = Field(default="add_ues")


class OAIDelSubscriberModel(NFVCLBaseModel):
    type: Literal["OpenAirInterface"] = Field(default="OpenAirInterface")
    operation: Literal["del_ues"] = Field(default="del_ues")
    imsi: str = Field()


class OAIAddSliceModel(SubSliceProfiles):
    type: Literal["OpenAirInterface"] = Field(default="OpenAirInterface")
    operation: Literal["add_slice"] = Field(default="add_slice")
    area_id: Optional[int] = Field(default=None)


class OAIDelSliceModel(NFVCLBaseModel):
    type: Literal["OpenAirInterface"] = Field(default="OpenAirInterface")
    operation: Literal["del_slice"] = Field(default="del_slice")
    sliceId: str = Field()


class OAIAddTacModel(SubArea):
    type: Literal["OpenAirInterface"] = Field(default="OpenAirInterface")
    operation: Literal["add_tac"] = Field(default="add_tac")


class OAIDelTacModel(SubArea):
    type: Literal["OpenAirInterface"] = Field(default="OpenAirInterface")
    operation: Literal["del_tac"] = Field(default="del_tac")


class OAIModelServices(NFVCLBaseModel):
    amf: K8sService = Field(alias="oai-amf-svc-lb")
    ausf: K8sService = Field(alias="oai-ausf-svc-lb")
    nrf: K8sService = Field(alias="oai-nrf-svc-lb")
    smf: K8sService = Field(alias="oai-smf-svc-lb")
    udm: K8sService = Field(alias="oai-udm-svc-lb")
    udr: K8sService = Field(alias="oai-udr-svc-lb")
    mysql: K8sService = Field()


class SMFHostAliases(NFVCLBaseModel):
    ip: str = Field()
    hostnames: str = Field()


class DNN(NFVCLBaseModel):
    dnn: str = Field()
    pdu_session_type: str = Field(default="IPv4")
    ipv4_range: str = Field()
    ipv6_prefix: str = Field(default="2001:1:2::/64")


class SessionManagementSubscription(NFVCLBaseModel):
    nssai_st: int = Field()
    nssai_sd: str = Field(default="")
    dnn: str = Field()
    default_session_type: str = Field(default="IPv4")  # Not present in payload
    session_ambr_ul: str = Field(default="1000Mbps")
    session_ambr_dl: str = Field(default="1000Mbps")
    qos_profile_5qi: int = Field()
    default_ssc_mode: int = Field(default=1)
    qos_profile_priority_level: int = Field(default=1)
    qos_profile_arp_priority_level: int = Field(default=15)
    qos_profile_arp_preemptcap: str = Field(default="NOT_PREEMPT")
    qos_profile_arp_preemptvuln: str = Field(default="NOT_PREEMPT")


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


class N2(NFVCLBaseModel):
    interface_name: str
    port: int


class Amf(NFVCLBaseModel):
    host: str
    sbi: Sbi
    n2: N2


class N4(NFVCLBaseModel):
    interface_name: str
    port: int


class Smf(NFVCLBaseModel):
    host: str
    sbi: Sbi
    n4: N4


class N3(NFVCLBaseModel):
    interface_name: str
    port: int


class N6(NFVCLBaseModel):
    interface_name: str


class N9(NFVCLBaseModel):
    interface_name: str
    port: int


class Upf(NFVCLBaseModel):
    host: str
    sbi: Sbi
    n3: N3
    n4: N4
    n6: N6
    n9: N9


class Udm(NFVCLBaseModel):
    host: str
    sbi: Sbi


class Udr(NFVCLBaseModel):
    host: str
    sbi: Sbi


class Ausf(NFVCLBaseModel):
    host: str
    sbi: Sbi


class Nrf(NFVCLBaseModel):
    host: str
    sbi: Sbi


class Nfs(NFVCLBaseModel):
    amf: Amf
    smf: Smf
    upf: Upf
    udm: Udm
    udr: Udr
    ausf: Ausf
    nrf: Nrf


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


class Amf1(NFVCLBaseModel):
    amf_name: str
    support_features_options: SupportFeaturesOptions
    relative_capacity: int
    statistics_timer_interval: int
    emergency_support: bool
    served_guami_list: List[ServedGuamiListItem]
    plmn_support_list: List[PlmnSupportListItem]
    supported_integrity_algorithms: List[str]
    supported_encryption_algorithms: List[str]


class SupportFeaturesSmf(NFVCLBaseModel):
    use_local_subscription_info: str
    use_local_pcc_rules: str


class Config(NFVCLBaseModel):
    enable_usage_reporting: str = Field(default="no")


class UpfAvailable(NFVCLBaseModel):
    host: str
    config: Config = Field(default=Config())


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


class Smf1(NFVCLBaseModel):
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


class SNssaiUpfInfoListItem(NFVCLBaseModel):
    sNssai: Snssai
    dnnUpfInfoList: List[DnnItem]


class UpfInfo(NFVCLBaseModel):
    sNssaiUpfInfoList: List[SNssaiUpfInfoListItem]


class Upf2(NFVCLBaseModel):
    support_features: SupportFeaturesUpf
    remote_n6_gw: str
    upf_info: UpfInfo


class Dnn(NFVCLBaseModel):
    dnn: str
    pdu_session_type: str = Field(default="IPV4")
    ipv4_subnet: str


class Currentconfig(NFVCLBaseModel):
    log_level: LogLevel
    register_nf: RegisterNf
    http_version: int
    snssais: List[Snssai]
    nfs: Nfs
    database: Database
    amf: Amf1
    smf: Smf1
    upf: Upf2
    dnns: List[Dnn]


class Baseconfig(NFVCLBaseModel):
    log_level: LogLevel
    register_nf: RegisterNf
    http_version: int
    snssais: List[Snssai]
    nfs: Nfs
    database: Database
    dnns: List[Dnn]


class Coreconfig(Baseconfig):
    amf: Amf1
    smf: Smf1


class Upfconfig(Baseconfig):
    upf: Upf2


class Global(NFVCLBaseModel):
    nfConfigurationConfigMap: str
    clusterIpServiceIpAllocation: bool
    waitForNRF: bool
    http2Param: str
    timeout: int


class Service(NFVCLBaseModel):
    annotations: Dict[str, Any]
    type: str
    port: int


class ImagePullSecret(NFVCLBaseModel):
    name: str


class Persistence(NFVCLBaseModel):
    enabled: bool


class Mysql(NFVCLBaseModel):
    enabled: bool
    imagePullPolicy: str
    oai5gdatabase: str
    service: Service
    imagePullSecrets: List[ImagePullSecret]
    persistence: Persistence


class Nfimage(NFVCLBaseModel):
    repository: str
    version: str
    pullPolicy: str


class ConfigPod(NFVCLBaseModel):
    logLevel: str


class OaiNrf(NFVCLBaseModel):
    enabled: bool
    kubernetesType: str
    nfimage: Nfimage
    includeTcpDumpContainer: bool
    imagePullSecrets: List[ImagePullSecret]
    config: ConfigPod
    nodeSelector: Dict[str, Any]


class OaiUdr(NFVCLBaseModel):
    enabled: bool
    kubernetesType: str
    nfimage: Nfimage
    includeTcpDumpContainer: bool
    imagePullSecrets: List[ImagePullSecret]
    config: ConfigPod
    nodeSelector: Dict[str, Any]


class OaiUdm(NFVCLBaseModel):
    enabled: bool
    kubernetesType: str
    nfimage: Nfimage
    includeTcpDumpContainer: bool
    imagePullSecrets: List[ImagePullSecret]
    config: ConfigPod
    nodeSelector: Dict[str, Any]


class OaiAusf(NFVCLBaseModel):
    enabled: bool
    kubernetesType: str
    nfimage: Nfimage
    includeTcpDumpContainer: bool
    imagePullSecrets: List[ImagePullSecret]
    config: ConfigPod
    nodeSelector: Dict[str, Any]


class Route(NFVCLBaseModel):
    dst: str
    gw: str


class N2Interface(NFVCLBaseModel):
    create: bool
    Ipadd: str
    Netmask: str
    Gateway: Any
    routes: List[Route]
    hostInterface: str


class MultusAmf(NFVCLBaseModel):
    defaultGateway: str
    n2Interface: N2Interface


class OaiAmf(NFVCLBaseModel):
    enabled: bool
    kubernetesType: str
    nfimage: Nfimage
    includeTcpDumpContainer: bool
    imagePullSecrets: List[ImagePullSecret]
    multus: MultusAmf
    nodeSelector: Dict[str, Any]


class N3Interface(NFVCLBaseModel):
    create: bool
    Ipadd: str
    Netmask: str
    Gateway: str
    routes: List[Route]
    hostInterface: str


class N4Interface(NFVCLBaseModel):
    create: bool
    Ipadd: str
    Netmask: str
    Gateway: str
    routes: str
    hostInterface: str


class N6Interface(NFVCLBaseModel):
    create: bool
    Ipadd: str
    Netmask: str
    Gateway: str
    routes: str
    hostInterface: str


class MultusUpf(NFVCLBaseModel):
    defaultGateway: str
    n3Interface: N3Interface
    n4Interface: N4Interface
    n6Interface: N6Interface


class OaiUpf(NFVCLBaseModel):
    enabled: bool
    kubernetesType: str
    nfimage: Nfimage
    includeTcpDumpContainer: bool
    imagePullSecrets: List[ImagePullSecret]
    multus: MultusUpf
    nodeSelector: Dict[str, Any]


class HostAliase(NFVCLBaseModel):
    ip: str
    hostnames: str


class N4InterfaceMultusSmf(NFVCLBaseModel):
    create: bool
    Ipadd: str
    Netmask: str
    Gateway: str
    hostInterface: str


class MultusSmf(NFVCLBaseModel):
    defaultGateway: str
    n4Interface: N4InterfaceMultusSmf


class OaiSmf(NFVCLBaseModel):
    enabled: bool
    kubernetesType: str
    nfimage: Nfimage
    includeTcpDumpContainer: bool
    hostAliases: List[HostAliase]
    multus: MultusSmf
    imagePullSecrets: List[ImagePullSecret]
    nodeSelector: Dict[str, Any]


class OaiValuesModel(NFVCLBaseModel):
    global_: Optional[Global] = Field(None, alias='global')
    mysql: Optional[Mysql] = None
    oai_nrf: Optional[OaiNrf] = Field(None, alias='oai-nrf')
    oai_udr: Optional[OaiUdr] = Field(None, alias='oai-udr')
    oai_udm: Optional[OaiUdm] = Field(None, alias='oai-udm')
    oai_ausf: Optional[OaiAusf] = Field(None, alias='oai-ausf')
    oai_amf: Optional[OaiAmf] = Field(None, alias='oai-amf')
    oai_upf: Optional[OaiUpf] = Field(None, alias='oai-upf')
    oai_smf: Optional[OaiSmf] = Field(None, alias='oai-smf')
    currentconfig: Optional[Currentconfig] = Field(None, alias='currentconfig')

class OaiCoreValuesModel(NFVCLBaseModel):
    global_: Optional[Global] = Field(None, alias='global')
    mysql: Optional[Mysql] = None
    oai_nrf: Optional[OaiNrf] = Field(None, alias='oai-nrf')
    oai_udr: Optional[OaiUdr] = Field(None, alias='oai-udr')
    oai_udm: Optional[OaiUdm] = Field(None, alias='oai-udm')
    oai_ausf: Optional[OaiAusf] = Field(None, alias='oai-ausf')
    oai_amf: Optional[OaiAmf] = Field(None, alias='oai-amf')
    oai_smf: Optional[OaiSmf] = Field(None, alias='oai-smf')
    coreconfig: Optional[Coreconfig] = Field(None, alias='currentconfig')

class OaiUpfValuesModel(NFVCLBaseModel):
    upfconfig: Optional[Upfconfig] = Field(None, alias='currentconfig')


class OAIModel(OAIBlueCreateModel):
    core_services: Optional[OAIModelServices] = Field(default=None)
    oai_config_values: Optional[OaiValuesModel] = Field(default=None)
    upf_config_dict: Dict[int, Currentconfig] = {}
    ue_dict: Dict[str, List[Snssai]] = {}


class BlueprintOAIBaseModel(Blueprint5GBaseModel):
    blue_model_5g: Optional[OAIModel] = Field(default=None)


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
