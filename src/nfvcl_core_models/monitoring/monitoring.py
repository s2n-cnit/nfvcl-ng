from typing import List

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.monitoring.prometheus_model import PrometheusTargetModel


class GrafanaDashboard(NFVCLBaseModel):
    name: str = Field()
    path: str = Field()

class BlueprintMonitoringDefinition(NFVCLBaseModel):
    prometheus_targets: List[PrometheusTargetModel] = Field(default_factory=list)
    grafana_dashboards: List[GrafanaDashboard] = Field(default_factory=list)
