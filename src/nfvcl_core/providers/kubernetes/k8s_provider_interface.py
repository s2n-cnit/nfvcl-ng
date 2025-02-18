from __future__ import annotations

import abc
from typing import Any, Dict, Optional

from nfvcl_core_models.network.ipam_models import SerializableIPv4Address

from nfvcl_core_models.network.network_models import MultusInterface
from nfvcl_core.providers.blueprint_ng_provider_interface import BlueprintNGProviderData, \
    BlueprintNGProviderInterface
from nfvcl_core_models.resources import HelmChartResource


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

    @abc.abstractmethod
    def reserve_k8s_multus_ip(self, area: int, network_name: str) -> MultusInterface:
        pass

    @abc.abstractmethod
    def release_k8s_multus_ip(self, area: int, network_name: str, ip_address: SerializableIPv4Address) -> MultusInterface:
        pass
