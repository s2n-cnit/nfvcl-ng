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


class K8sDaemon(str, Enum):
    FLANNEL = 'flannel'
    OPEN_EBS = 'openebs-ndm'
    METALLB = 'metallb'
    CALICO = 'calico-node'


class K8sVersion(str, Enum):
    V1_24 = 'v1.24'
    V1_25 = 'v1.25'
    V1_26 = 'v1.26'
    V1_27 = 'v1.27'

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class K8sPluginName(str, Enum):
    """

    """
    FLANNEL = 'flannel'
    OPEN_EBS = 'openebs'
    METALLB = 'metallb'
    CALICO = 'calico'


class K8sPluginType(str, Enum):
    """
    Represent the type of plugins that can be installed. This is useful to understand if there are conflicts
    when installing plugins.
    """
    NETWORK = 'network'
    STORAGE = 'storage'
    METALLB = 'metallb'


class K8sPlugin(BaseModel):
    """
    Plugin representation
    """
    name: K8sPluginName = Field(description="Plugin name")
    type: K8sPluginType = Field(description="Type of plugin, must me a valid value in enum K8sPluginType")
    installation_modules: List[str] = Field(default=[], description="List of modules to be installed when adding plugin"
                                                                    " to cluster")
    daemon_sets: List = Field(default=[], description="List of daemon sets present when the plugin is correctly "
                                                      "installed")
