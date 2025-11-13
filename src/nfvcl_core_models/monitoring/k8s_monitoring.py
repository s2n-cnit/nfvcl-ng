

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel


class DestinationType(str, Enum):
    PROMETHEUS = 'prometheus'
    LOKI = 'loki'


class Cluster(NFVCLBaseModel):
    name: str
    namespace: str


class Global(NFVCLBaseModel):
    platform: str
    kubernetes_api_service: str = Field(..., alias='kubernetesAPIService')
    scrape_interval: str = Field(..., alias='scrapeInterval')
    max_cache_size: int = Field(..., alias='maxCacheSize')


class BasicAuth(NFVCLBaseModel):
    username: str
    password: str


class Destination(NFVCLBaseModel):
    name: str
    type: str
    url: str
    basic_auth: Optional[BasicAuth] = Field(default=None, alias='basicAuth')


class LabelMatchers(NFVCLBaseModel):
    app_kubernetes_io_name: Any = Field(default=None, alias='app.kubernetes.io/name')
    component: str = Field(default="node-exporter", alias='app.kubernetes.io/component')


class Service(NFVCLBaseModel):
    port: int = Field(default=9101, alias='port')
    target_port: int = Field(default=9101, alias='targetPort')


class NodeExporter(NFVCLBaseModel):
    deploy: bool = Field(default=False, alias='deploy')
    label_matchers: Optional[LabelMatchers] = Field(default=None, alias='labelMatchers')
    service: Optional[Service] = Field(default_factory=Service, alias='service')


class MetricsTuning(NFVCLBaseModel):
    include_metrics: List = Field(..., alias='includeMetrics')
    exclude_metrics: List = Field(..., alias='excludeMetrics')
    use_default_allow_list: bool = Field(..., alias='useDefaultAllowList')
    drop_empty_container_labels: bool = Field(..., alias='dropEmptyContainerLabels')
    drop_empty_image_labels: bool = Field(..., alias='dropEmptyImageLabels')
    keep_physical_filesystem_devices: List = Field(
        ..., alias='keepPhysicalFilesystemDevices'
    )
    keep_physical_network_devices: List = Field(..., alias='keepPhysicalNetworkDevices')


class Cadvisor(NFVCLBaseModel):
    enabled: bool
    job_label: str = Field(..., alias='jobLabel')
    metrics_tuning: MetricsTuning = Field(..., alias='metricsTuning')


class K8sMetrics(NFVCLBaseModel):
    enabled: bool
    destinations: Optional[List[str]] = Field(default_factory=list, alias='destinations')
    collector: str


class ClusterMetrics(K8sMetrics):
    cadvisor: Cadvisor
    node_exporter: Optional[NodeExporter] = Field(..., alias='node-exporter')


# class ClusterEvents(NFVCLBaseModel):
#     pass


# class NodeLogs(NFVCLBaseModel):
#     pass


# class PodLogs(NFVCLBaseModel):
#     pass


class ApplicationObservability(NFVCLBaseModel):
    enabled: bool
    destinations: Optional[List[str]] = Field(default_factory=list, alias='destinations')
    receivers: Dict[str, Any]
    collector: str


# class AutoInstrumentation(NFVCLBaseModel):
#     pass


# class AnnotationAutodiscovery(NFVCLBaseModel):
#     pass


# class PrometheusOperatorObjects(NFVCLBaseModel):
#     pass


# class Profiling(NFVCLBaseModel):
#     pass


class Integrations(NFVCLBaseModel):
    destinations: Optional[List[str]] = Field(default_factory=list, alias='destinations')
    collector: str


class SelfReporting(NFVCLBaseModel):
    enabled: bool
    destinations: Optional[List[str]] = Field(default_factory=list, alias='destinations')
    scrape_interval: str = Field(..., alias='scrapeInterval')


class MetricsEnabler(NFVCLBaseModel):
    enabled: bool


# class AlloyMetrics(NFVCLBaseModel):
#     enabled: bool


# class AlloySingleton(NFVCLBaseModel):
#     enabled: bool


# class AlloyLogs(NFVCLBaseModel):
#     enabled: bool


class Alloy(NFVCLBaseModel):
    extra_ports: List = Field(..., alias='extraPorts')


class ExtraService(NFVCLBaseModel):
    enabled: bool
    name: str
    fullname: str


class AlloyReceiver(NFVCLBaseModel):
    enabled: bool
    alloy: Alloy
    extra_service: ExtraService = Field(..., alias='extraService')


# class AlloyProfiles(NFVCLBaseModel):
#     enabled: bool


class AlloyOperator(NFVCLBaseModel):
    deploy: bool


class K8sMonitoring(NFVCLBaseModel):
    cluster: Optional[Cluster] = None
    global_: Optional[Global] = Field(None, alias='global')
    destinations: Optional[List[Destination]] = Field(default_factory=list, alias='destinations')
    cluster_metrics: Optional[ClusterMetrics] = Field(None, alias='clusterMetrics')
    cluster_events: Optional[K8sMetrics] = Field(None, alias='clusterEvents')
    node_logs: Optional[K8sMetrics] = Field(None, alias='nodeLogs')
    pod_logs: Optional[K8sMetrics] = Field(None, alias='podLogs')
    application_observability: Optional[ApplicationObservability] = Field(None, alias='applicationObservability')
    auto_instrumentation: Optional[K8sMetrics] = Field(None, alias='autoInstrumentation')
    annotation_autodiscovery: Optional[K8sMetrics] = Field(None, alias='annotationAutodiscovery')
    prometheus_operator_objects: Optional[K8sMetrics] = Field(None, alias='prometheusOperatorObjects')
    profiling: Optional[K8sMetrics] = None
    integrations: Optional[Integrations] = None
    self_reporting: Optional[SelfReporting] = Field(None, alias='selfReporting')
    alloy_metrics: Optional[MetricsEnabler] = Field(None, alias='alloy-metrics')
    alloy_singleton: Optional[MetricsEnabler] = Field(None, alias='alloy-singleton')
    alloy_logs: Optional[MetricsEnabler] = Field(None, alias='alloy-logs')
    alloy_receiver: Optional[AlloyReceiver] = Field(None, alias='alloy-receiver')
    alloy_profiles: Optional[MetricsEnabler] = Field(None, alias='alloy-profiles')
    alloy_operator: Optional[AlloyOperator] = Field(None, alias='alloy-operator')
    extra_objects: Optional[List] = Field(None, alias='extraObjects')

    def add_destination(self, name: str, _type: DestinationType, url: str, username: str = None, password: str = None) -> None:
        destination = Destination(name=name, type=_type, url=url)
        if username and password:
            auth = BasicAuth(
                username=username,
                password=password
            )
            destination.basic_auth = auth
        if destination not in self.destinations:
            self.destinations.append(destination)
            match _type:
                case DestinationType.LOKI:
                    self.alloy_logs.enabled = True

                    self.cluster_events.enabled = True
                    self.cluster_events.destinations.append(name)

                    self.node_logs.enabled = True
                    self.node_logs.destinations.append(name)

                    self.pod_logs.enabled = True
                    self.pod_logs.destinations.append(name)
                case DestinationType.PROMETHEUS:
                    self.alloy_metrics.enabled = True

                    self.cluster_metrics.enabled = True
                    self.cluster_metrics.destinations.append(name)
                case _:
                    pass

    def del_destination(self, name: str) -> None:
        for destination in self.destinations.copy():
            if destination.name == name:
                match destination.type:
                    case DestinationType.LOKI:
                        self.cluster_events.destinations.remove(name)
                        if len(self.cluster_events.destinations) == 0:
                            self.cluster_events.enabled = False

                        self.node_logs.destinations.remove(name)
                        if len(self.node_logs.destinations) == 0:
                            self.node_logs.enabled = False

                        self.pod_logs.destinations.remove(name)
                        if len(self.pod_logs.destinations) == 0:
                            self.pod_logs.enabled = False

                        if (not self.pod_logs.enabled) and (not self.node_logs.enabled) and (not self.cluster_events.enabled):
                            self.alloy_logs.enabled = False
                    case DestinationType.PROMETHEUS:

                        self.cluster_metrics.destinations.remove(name)
                        if len(self.cluster_metrics.destinations) == 0:
                            self.cluster_metrics.enabled = False
                            self.alloy_metrics.enabled = False
                    case _:
                        pass
                self.destinations.remove(destination)
            else:
                self.logger.warning("Destination %s is not defined", name)

    def enable_node_exporter(self, label: str = None):
        self.cluster_metrics.node_exporter.deploy = True
        if label and len(label) > 0:
            self.cluster_metrics.node_exporter.label = label
