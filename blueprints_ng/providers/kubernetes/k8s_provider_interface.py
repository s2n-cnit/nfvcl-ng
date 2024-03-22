from __future__ import annotations

import abc
from typing import Any, Dict

from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderData, \
    BlueprintNGProviderInterface
from blueprints_ng.resources import HelmChartResource


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
