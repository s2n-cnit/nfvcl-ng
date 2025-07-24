from enum import Enum
from typing import List, Optional

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.monitoring.k8s_monitoring import K8sMonitoring
from nfvcl_core_models.monitoring.loki_model import LokiServerModel
from nfvcl_core_models.monitoring.prometheus_model import PrometheusServerModel
from nfvcl_core_models.network.network_models import SerializableIPv4Address


class K8sPluginName(str, Enum):
    """
    Supported plugin names by the k8s manager
    """
    FLANNEL = 'flannel'
    OPEN_EBS = 'openebs'
    METALLB = 'metallb'
    CALICO = 'calico'
    METRIC_SERVER = 'metric-server'
    MULTUS = 'multus'
    K8S_MONITORING = 'k8s-monitoring'
    ISTIO = 'istio'
    CADVISOR = 'cadvisor'
    CERT_MANAGER = 'cert-manager'
    NFVCL_WEBHOOK = 'nfvcl-webhook'


class K8sPluginType(str, Enum):
    """
    Represent the type of plugins that can be installed. This is useful to understand if there are conflicts
    when installing plugins.
    """
    NETWORK = 'network'
    STORAGE = 'storage'
    METALLB = 'metallb'
    GENERIC = 'generic'
    MONITORING = 'monitoring'


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


class K8sLoadBalancerPoolArea(NFVCLBaseModel):
    """
    Represents name and ip_list to be used for a load balancer pool of a load balancer.
    Hostnames are used to bind L2 advertisement to these hosts.
    """
    pool_name: str = Field(pattern=r"^([a-z0-9]+(-[a-z0-9]+)*)$")
    ip_list: List[SerializableIPv4Address] = Field(description="List of IP addresses for LB")
    host_names: Optional[List[str]] = Field(default=None, description="List of hostnames enabled to announce al L2 the LB pool, if none announce on all nodes.")


class K8sPluginAdditionalData(NFVCLBaseModel):
    """
    Model that represent data to be used for filling the k8s plugin template files.
    """
    areas: Optional[List[K8sLoadBalancerPoolArea]] = Field(default=None, description="The list of load balancer pool areas for MetalLB configuration")
    pod_network_cidr: Optional[str] = Field(default=None, description="The pod network cidr used for Flannel/Calico installation. If None it is retrieved from the cluster.")
    cadvisor_node_port: Optional[int] = Field(default=None, description="The node port used by the service to expose the DaemonSet")
    loki: Optional[LokiServerModel] = Field(default=None, description="The Loki info")
    prometheus: Optional[PrometheusServerModel] = Field(default=None, description="The Prometheus info")
    k8smonitoring_node_exporter_enabled: Optional[bool] = Field(default=False, description="Whether the node exporter should be enabled")
    k8smonitoring_node_exporter_label: Optional[str] = Field(default=None, description="The label of another node exporter already running on the cluster")
    k8smonitoring_config: Optional[K8sMonitoring] = Field(default=None, description="The K8s monitoring configuration")


class K8sPluginsToInstall(NFVCLBaseModel):
    """
    Model used to represent a list of plugins to be installed with specific parameters needed by the plugins.
    """
    plugin_list: List[K8sPluginName] = Field(description="The list of plugins to be installed")
    load_balancer_pool: Optional[K8sLoadBalancerPoolArea] = Field(default=None, description="The pool to be used by the Load Balancer to expose LB services.")
    skip_plug_checks: bool = Field(default=False, description="If True do not check for plugin compatibility")


class K8sPluginToUninstall(NFVCLBaseModel):
    namespace: str = Field()


class K8sOperationType(str, Enum):
    """
    Types of operation supported from k8s management engine
    """
    INSTALL_PLUGIN = 'install_plugin'
    APPLY_YAML = 'apply_yaml'


class K8sMonitoringConfig(NFVCLBaseModel):
    loki_id: Optional[str] = Field(default="", description="The loki server id")
    prometheus_id: Optional[str] = Field(default="", description="The prometheus server id")
    node_exporter_enabled: Optional[bool] = Field(default=False)
    node_exporter_label: Optional[str] = Field(default=None)
