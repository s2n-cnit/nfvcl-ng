from typing import List, Optional, Dict, Any

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.linux.ip import Route
from nfvcl_models.blueprint_ng.free5gc.free5gcCore import Nnetwork, Nif
from nfvcl_models.blueprint_ng.g5.common5g import Slice5G
from nfvcl_models.blueprint_ng.g5.custom_types_5g import KEYType, OPCType, IMSIType, MCCType, MNCType, DNNType, SUPIType
from nfvcl_models.blueprint_ng.g5.ue import OpType, UESession


class Image(NFVCLBaseModel):
    name: str
    tag: str
    pullPolicy: str


class Global(NFVCLBaseModel):
    n2network: Nnetwork
    n3network: Nnetwork
    image: Image


class Model(NFVCLBaseModel):
    image: Image


class N2if(NFVCLBaseModel):
    ipAddress: str


class N3if(NFVCLBaseModel):
    ipAddress: str


class AmfN2if(NFVCLBaseModel):
    ipAddress: str
    port: int


class Ngap(NFVCLBaseModel):
    enabled: bool


class Service(NFVCLBaseModel):
    ngap: Ngap


class Amf(NFVCLBaseModel):
    n2if: AmfN2if
    service: Service


class GNBConfiguration(NFVCLBaseModel):
    mcc: MCCType
    mnc: MNCType
    nci: str
    idLength: int
    tac: int
    slices: List[Slice5G]
    ignoreStreamIds: Optional[bool] = Field(default=True)


class GnbService(NFVCLBaseModel):
    name: str
    type: Optional[str] = Field(default='LoadBalancer')
    port: Optional[int] = Field(default=4997)
    protocol: Optional[str] = Field(default='UDP')


class Gnb(NFVCLBaseModel):
    additional_routes: List[str] = Field(default=[])
    enabled: bool
    name: str
    n2if: N2if
    n3if: N3if
    amf: Amf
    configuration: GNBConfiguration
    service: GnbService


class UacAic(NFVCLBaseModel):
    mps: Optional[bool] = Field(default=False)
    mcs: Optional[bool] = Field(default=False)


class UacAcc(NFVCLBaseModel):
    normalClass: Optional[int] = Field(default=0)
    class11: Optional[bool] = Field(default=False)
    class12: Optional[bool] = Field(default=False)
    class13: Optional[bool] = Field(default=False)
    class14: Optional[bool] = Field(default=False)
    class15: Optional[bool] = Field(default=False)


class Integrity(NFVCLBaseModel):
    IA1: Optional[bool] = Field(default=True)
    IA2: Optional[bool] = Field(default=True)
    IA3: Optional[bool] = Field(default=True)


class Ciphering(NFVCLBaseModel):
    EA1: Optional[bool] = Field(default=True)
    EA2: Optional[bool] = Field(default=True)
    EA3: Optional[bool] = Field(default=True)


class IntegrityMaxRate(NFVCLBaseModel):
    uplink: Optional[str] = Field(default="full")
    downlink: Optional[str] = Field(default="full")


class UEConfiguration(NFVCLBaseModel):
    supi: SUPIType
    protectionScheme: int = Field(default=0)
    homeNetworkPublicKey: str = Field(default="5a8d38864820197c3394b92613b20b91633cbd897119273bf8e4a6f4eec0a650")
    homeNetworkPublicKeyId: int = Field(default=1)
    routingIndicator: str = Field(default="0000")
    mcc: MCCType
    mnc: MNCType
    key: KEYType
    op: OPCType
    opType: OpType
    amf: Optional[int] = Field(default=None)
    imei: Optional[str] = Field(default=None)
    imeiSv: Optional[str] = Field(default=None)
    uacAic: Optional[UacAic] = Field(default_factory=UacAic)
    uacAcc: Optional[UacAcc] = Field(default_factory=UacAcc)
    sessions: List[UESession]
    configured_nssai: List[Slice5G] = Field(alias='configured-nssai')
    default_nssai: List[Slice5G] = Field(alias='default-nssai')
    integrity: Optional[Integrity] = Field(default_factory=Integrity)
    ciphering: Optional[Ciphering] = Field(default_factory=Ciphering)
    integrityMaxRate: IntegrityMaxRate = Field(default_factory=IntegrityMaxRate)


class Configmap(NFVCLBaseModel):
    name: str


class Volume(NFVCLBaseModel):
    name: str
    mount: Optional[str] = Field(default="/etc/ueransim")  # "/ueransim/config"


class Requests(NFVCLBaseModel):
    cpu: Optional[str] = Field(default="100m")
    memory: Optional[str] = Field(default="128Mi")


class Resources(NFVCLBaseModel):
    requests: Optional[Requests] = Field(default_factory=Requests)


class Capabilities(NFVCLBaseModel):
    add: List[str] = Field(default=["NET_ADMIN"])


class SecurityContext(NFVCLBaseModel):
    capabilities: Capabilities = Field(default_factory=Capabilities)


class UeInstance(NFVCLBaseModel):
    name: str
    replicaCount: Optional[int] = Field(default=1)
    configmap: Configmap
    volume: Volume
    command: Optional[str] = Field(default="/usr/local/bin/nr-ue -c /etc/ueransim/ue.yaml")  # "./nr-ue -c ./config/ue-config.yaml"
    script: Optional[str] = Field(default="")
    podAnnotations: Dict[str, Any] = Field(default_factory=dict)
    imagePullSecrets: Optional[List] = Field(default_factory=list)
    podSecurityContext: Dict[str, Any] = Field(default_factory=dict)
    securityContext: Optional[SecurityContext] = Field(default_factory=SecurityContext)
    resources: Optional[Resources] = Field(default_factory=Resources)
    nodeSelector: Dict[str, Any] = Field(default_factory=dict)
    tolerations: Optional[List] = Field(default_factory=list)
    affinity: Dict[str, Any] = Field(default_factory=dict)
    configuration: UEConfiguration


class Ues(NFVCLBaseModel):
    enabled: bool
    instances: List[UeInstance]


class UeransimK8sModel(NFVCLBaseModel):
    global_: Optional[Global] = Field(None, alias='global')
    gnb: Optional[Gnb] = None
    ue: Optional[Ues] = None
