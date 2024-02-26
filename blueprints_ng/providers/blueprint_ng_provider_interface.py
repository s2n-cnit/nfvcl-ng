from __future__ import annotations

import abc
from typing import Any, Dict

from utils.log import create_logger

from blueprints_ng.resources import VmResource, VmResourceConfiguration, HelmChartResource, HardwareResourceConfiguration
from models.base_model import NFVCLBaseModel


class BlueprintNGProviderData(NFVCLBaseModel):
    pass


class BlueprintNGProviderException(Exception):
    pass


class BlueprintNGProviderInterface(abc.ABC):
    data: BlueprintNGProviderData

    def __init__(self, blueprint):
        super().__init__()
        self.logger = create_logger(self.__class__.__name__, blueprintid=blueprint.id)

    @abc.abstractmethod
    def create_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration):
        if not vm_resource_configuration.vm_resource.created:
            raise BlueprintNGProviderException("VM Resource not created")

    @abc.abstractmethod
    def destroy_vm(self, vm_resource: VmResource):
        pass

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
    def configure_hardware(self, hardware_resource_configuration: HardwareResourceConfiguration):
        pass
        # TODO check if not in use?
        # if not hardware_resource_configuration.vm_resource.created:
        #     raise BlueprintNGProviderException("VM Resource not created")
