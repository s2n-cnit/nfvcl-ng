from __future__ import annotations

import abc
from typing import Any, Dict, Optional

from nfvcl.blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderData, \
    BlueprintNGProviderInterface
from nfvcl.blueprints_ng.resources import HelmChartResource


class K8SProviderData(BlueprintNGProviderData):
    pass


class K8SProviderException(Exception):
    pass


class K8SProviderInterface(BlueprintNGProviderInterface):
    data: K8SProviderData

    @abc.abstractmethod
    def install_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        pass

    @abc.abstractmethod
    def update_values_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        pass

    @abc.abstractmethod
    def uninstall_helm_chart(self, helm_chart_resource: HelmChartResource):
        pass

    @abc.abstractmethod
    def get_pod_log(self, helm_chart_resource: HelmChartResource, pod_name: str, tail_lines: Optional[int]=None) -> str:
        pass
