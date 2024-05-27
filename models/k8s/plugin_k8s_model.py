from enum import Enum
from typing import List

from pydantic import Field, field_validator

from models.base_model import NFVCLBaseModel
from models.k8s.common_k8s_model import LBPool


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


class K8sPluginLabel(NFVCLBaseModel):
    """
    Describe a K8s object used to recognized installed plugins on cluster.
    Tha label and values are used to identify a resource in a namespace with a certain name.
    """
    namespace: str
    name: str
    label: str
    value: str


class K8sPlugin(NFVCLBaseModel):
    """
    Plugin representation
    """
    name: K8sPluginName = Field(description="Plugin name")
    type: K8sPluginType = Field(description="Type of plugin, must me a valid value in enum K8sPluginType")
    installation_modules: List[str] = Field(default=[], description="List of modules to be installed when adding plugin"
                                                                    " to cluster")
    daemon_sets: List[K8sPluginLabel] = Field(default=[],
                                              description="List of daemon sets present when the plugin is correctly "
                                                          "installed")
    deployments: List[K8sPluginLabel] = Field(default=[], description="List of deployments present when the plugin"
                                                                      "is correctly installed on the cluster.")


class K8sTemplateFillData(NFVCLBaseModel):
    """
    Model that represent data to be used for filling the plugin template files.
    CIDR is used by flannel and calico.
    lb_ipaddresses is used by metal-lb to give of IPs for load balancers (used automatically)
    lb_ipaddresses is used by metal-lb to give a pool of IPs for load balancers (must be enabled with metal lb call)
    """
    pod_network_cidr: str = Field(default="")
    lb_ipaddresses: List[str] = Field(default=[])
    lb_ipaddresses_auto: List[str] = Field(default=[])
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


class K8sPluginsToInstall(NFVCLBaseModel):
    """
    Model used to represent a list of plugins to be installed with specific parameters needed by the plugins.
    """
    plugin_list: List[K8sPluginName]
    template_fill_data: K8sTemplateFillData = Field(default=K8sTemplateFillData())
    skip_plug_checks: bool = Field(default=False)


class K8sOperationType(str, Enum):
    """
    Types of operation supported from k8s management engine
    """
    INSTALL_PLUGIN = 'install_plugin'
    APPLY_YAML = 'apply_yaml'
