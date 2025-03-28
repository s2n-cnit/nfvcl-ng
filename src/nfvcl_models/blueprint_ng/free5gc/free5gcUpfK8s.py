from typing import List, Optional

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_models.blueprint_ng.free5gc.free5gcCore import Nnetwork
from nfvcl_models.blueprint_ng.g5.upf import DnnWithCidrModel


class Global(NFVCLBaseModel):
    project_name: str = Field(..., alias='projectName')
    user_plane_architecture: str = Field(default="single", alias='userPlaneArchitecture')
    uesubnet: List[str] = Field(default_factory=list, alias='uesubnet')
    n4network: Nnetwork
    n3network: Nnetwork
    n6network: Nnetwork
    n9network: Nnetwork


class Image(NFVCLBaseModel):
    name: str
    tag: str
    pull_policy: str = Field(..., alias='pullPolicy')


class Configmap(NFVCLBaseModel):
    wrapper_additional_commands: str = Field(..., alias='wrapperAdditionalCommands')


class Volume(NFVCLBaseModel):
    mount: str
    tlsmount: str


class Nif(NFVCLBaseModel):
    ip_address: str = Field(..., alias='ipAddress')


class Capabilities(NFVCLBaseModel):
    add: List[str]


class SecurityContext(NFVCLBaseModel):
    capabilities: Capabilities


class Requests(NFVCLBaseModel):
    cpu: str
    memory: str


class Resources(NFVCLBaseModel):
    requests: Requests


class ReadinessProbe(NFVCLBaseModel):
    initial_delay_seconds: int = Field(..., alias='initialDelaySeconds')
    period_seconds: int = Field(..., alias='periodSeconds')
    timeout_seconds: int = Field(..., alias='timeoutSeconds')
    failure_threshold: int = Field(..., alias='failureThreshold')
    success_threshold: int = Field(..., alias='successThreshold')


class LivenessProbe(NFVCLBaseModel):
    initial_delay_seconds: int = Field(..., alias='initialDelaySeconds')
    period_seconds: int = Field(..., alias='periodSeconds')
    timeout_seconds: int = Field(..., alias='timeoutSeconds')
    failure_threshold: int = Field(..., alias='failureThreshold')
    success_threshold: int = Field(..., alias='successThreshold')


class Autoscaling(NFVCLBaseModel):
    enabled: bool
    min_replicas: int = Field(..., alias='minReplicas')
    max_replicas: int = Field(..., alias='maxReplicas')
    target_cpu_utilization_percentage: int = Field(
        ..., alias='targetCPUUtilizationPercentage'
    )


class Logger(NFVCLBaseModel):
    enable: bool
    level: str
    report_caller: bool = Field(..., alias='reportCaller')


class Configuration(NFVCLBaseModel):
    dnn_list: List[DnnWithCidrModel] = Field(..., alias='dnnList')
    logger: Logger


class BaseUpf(NFVCLBaseModel):
    name: str
    configuration: Configuration


class Upf(BaseUpf):
    n3if: Nif
    n4if: Nif
    n6if: Nif


class UpfUlcl(BaseUpf):
    n9if: Nif
    n4if: Nif
    n6if: Nif


class Upfb(BaseUpf):
    n3if: Nif
    n9if: Nif
    n4if: Nif
    n6if: Nif


class Free5gcK8sUpfConfig(NFVCLBaseModel):
    global_: Optional[Global] = Field(None, alias='global')
    upf: Optional[Upf] = None
