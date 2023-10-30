from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, IPvAnyAddress, field_validator
from models.k8s.common_k8s_model import LBPool


class NfvoStatus(Enum):
    ONBOARDED = "onboarded"
    NOT_ONBOARDED = "not_onboarded"
    ONBOARDING = 'onboarding'
    ERROR = 'error'


class K8sVersion(str, Enum):
    """
    This class represent a k8s version. This should represent supported versions of k8s clusters by k8s manager.
    It has the utilities for checking if the version is present and to compare versions.
    """
    V1_24 = 'v1.24'
    V1_25 = 'v1.25'
    V1_26 = 'v1.26'
    V1_27 = 'v1.27'

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_

    def is_minor(self, to_compare) -> bool:
        """
        Check if this version is less than another

        Args:
            to_compare: the K8sVersion to be compared to this one

        Returns:
            true if this is minor
        """
        if not isinstance(to_compare, K8sVersion):
            return NotImplemented
        this_version = self.value[1:]
        other_version = to_compare.value[1:]
        return float(this_version) < float(other_version)


class K8sModel(BaseModel):
    name: str = Field(title="Name of k8s cluster. It must be unique for each k8s cluster")
    provided_by: str
    blueprint_ref: str = Field(default="", title="Reference blueprint, empty if k8s cluster is external")
    credentials: str = Field(title="Content of k8s crediential file (example admin.conf)")
    vim_name: Optional[str] = Field(default=None, title="Reference VIM, where k8s cluster is deployed.")
    k8s_version: K8sVersion = Field(default=K8sVersion.V1_24)
    networks: List[str] = Field(title="List of attached networks", min_items=1)
    areas: List[int] = Field(title="Competence areas", min_items=1)
    cni: Optional[str] = Field(default=None)
    nfvo_status: NfvoStatus = Field(default=NfvoStatus.NOT_ONBOARDED)
    nfvo_onboard: bool = Field(default=False)

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, K8sModel):
            return self.name == other.name
        return False


class K8sModelCreateFromBlueprint(BaseModel):
    name: str
    nfvo_onboard: bool = False
    blueprint_ref: str


class K8sPluginName(str, Enum):
    """
    Supported plugin names by the k8s manager
    """
    FLANNEL = 'flannel'
    OPEN_EBS = 'openebs'
    METALLB = 'metallb'
    CALICO = 'calico'
    METRIC_SERVER = 'metric-server'
    MULTUS = 'multus-cni'
    ISTIO = 'istio'


class K8sPluginType(str, Enum):
    """
    Represent the type of plugins that can be installed. This is useful to understand if there are conflicts
    when installing plugins.
    """
    NETWORK = 'network'
    STORAGE = 'storage'
    METALLB = 'metallb'
    GENERIC = 'generic'


class K8sPluginLabel(BaseModel):
    """
    Describe a K8s object used to recognized installed plugins on cluster.
    Tha label and values are used to identify a resource in a namespace with a certain name.
    """
    namespace: str
    name: str
    label: str
    value: str


class K8sPlugin(BaseModel):
    """
    Plugin representation
    """
    name: K8sPluginName = Field(description="Plugin name")
    type: K8sPluginType = Field(description="Type of plugin, must me a valid value in enum K8sPluginType")
    installation_modules: List[str] = Field(default=[], description="List of modules to be installed when adding plugin"
                                                                    " to cluster")
    daemon_sets: List[K8sPluginLabel] = Field(default=[], description="List of daemon sets present when the plugin is correctly "
                                                      "installed")
    deployments: List[K8sPluginLabel] = Field(default=[], description="List of deployments present when the plugin"
                                                                           "is correctly installed on the cluster.")


class K8sOperationType(str, Enum):
    """
    Types of operation supported from k8s management engine
    """
    INSTALL_PLUGIN = 'install_plugin'
    APPLY_YAML = 'apply_yaml'


class K8sModelManagement(BaseModel):
    """
    Model to support message exchange from NFVCL core and K8S management (through Redis sub/pub)
    """
    k8s_ops: K8sOperationType = Field(description="Type of operation to be applied at the desired cluser")
    cluster_id: str = Field(description="The identifier of the k8s cluster")
    data: str = Field(description="Data to be parsed, change depending on the operation type")
    options: dict = Field(default={}, description="Hold optional parameters for k8s management")


class K8sTemplateFillData(BaseModel):
    """
    Model that represent data to be used for filling the plugin template files.
    CIDR is used by flannel and calico.
    lb_ipaddresses is used by metal-lb to give of IPs for load balancers (used automatically)
    lb_ipaddresses is used by metal-lb to give a pool of IPs for load balancers (must be enabled with metal lb call)
    """
    pod_network_cidr: str = Field(default="")
    lb_ipaddresses: List[str] = Field(default=[])
    lb_pools: List[LBPool] = Field(default=[])

    @field_validator('lb_pools')
    @classmethod
    def validate_lb_pools(cls, pool_list: List[LBPool]) -> List[LBPool]:
        """
        K8s does not allow '_' in resource names and lower case.
        """
        to_ret: List[LBPool]
        if isinstance(pool_list, list):
            for pool in pool_list:
                pool.net_name = pool.net_name.replace("_", "-").lower()
            return pool_list

class K8sPluginsToInstall(BaseModel):
    """
    Model used to represent a list of plugins to be installed with specific parameters needed by the plugins.
    """
    plugin_list: List[K8sPluginName]
    template_fill_data: K8sTemplateFillData = Field(default=K8sTemplateFillData())
    skip_plug_checks: bool = Field(default=False)

class K8sQuota(BaseModel):
    request_cpu: str = Field(default=1, alias="requests.cpu")
    request_memory: str = Field(default="1Gi", alias="requests.memory")
    limit_cpu: str = Field(default=2, alias="limits.cpu")
    limit_memory: str = Field(default="2Gi", alias="limits.memory")
