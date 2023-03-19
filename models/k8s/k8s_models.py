from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, conlist


class K8sModel(BaseModel):
    name: str = Field(title="Name of k8s cluster")
    provided_by: str
    blueprint_ref: str = Field(default="", title="Reference blueprint, empty if k8s cluster is external")
    credentials: str = Field(title="Content of k8s crediential file (example admin.conf)")
    vim_name: str = Field(title="Reference VIM, where k8s cluster is deployed (example OpenStack)")
    k8s_version: str
    networks: List[str] = Field(title="List of attached networks", min_items=1)
    areas: List[str] = Field(title="Competence areas", min_items=1)
    cni: Optional[str]
    nfvo_status: str = 'not_onboarded'


class K8sModelCreateFromBlueprint(BaseModel):
    name: str
    nfvo_onboard: bool = False
    blueprint_ref: str


class K8sModelUpdateRequest(BaseModel):
    nfvo_onboard: bool = False
    networks: conlist(str, min_items=1)
    areas: conlist(int, min_items=1)


class K8sModelCreateFromExternalCluster(BaseModel):
    name: str
    nfvo_onboard: bool = False
    credentials: str
    vim_name: str
    k8s_version: str
    networks: conlist(str, min_items=1)
    areas: conlist(int, min_items=1)
    cni: Optional[str]

class K8sDaemons(Enum):
    FLANNEL = 'flannel'
    OPEN_EBS = 'openebs-ndm'
    METALLB = 'metallb'
