from enum import Enum
from typing import List, Optional

from pydantic import Field, field_validator

from nfvcl.models.base_model import NFVCLBaseModel


class K8sServiceType(str, Enum):
    """
    https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types
    """
    ClusterIP = "ClusterIP"
    NodePort = "NodePort"
    LoadBalancer = "LoadBalancer"
    ExternalName = "ExternalName"


class K8sServicePortProtocol(str, Enum):
    """
    https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.28/#serviceport-v1-core
    """
    TCP = "TCP"
    UDP = "UDP"
    SCTP = "SCTP"


class K8sServicePort(NFVCLBaseModel):
    """
    https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.28/#serviceport-v1-core
    """
    name: Optional[str] = Field(default=None)
    port: int = Field()
    protocol: K8sServicePortProtocol = Field()
    targetPort: int | str = Field()


class K8sService(NFVCLBaseModel):
    """
    https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.28/#service-v1-core
    """
    type: K8sServiceType = Field()
    name: str = Field()
    cluster_ip: Optional[str] = Field(default=None)
    external_ip: Optional[List[str]] = Field(default=None)
    ports: List[K8sServicePort] = Field(default=[])

    @field_validator('cluster_ip', 'external_ip')
    def none_str_to_none(cls, v):
        if v == 'None':
            return None
        return v

class K8sDeployment(NFVCLBaseModel):
    """
    https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.28/#deployment-v1-apps
    """
    name: str = Field()

class K8sStatefulSet(NFVCLBaseModel):
    """
    https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.28/#deployment-v1-apps
    """
    name: str = Field()
