from __future__ import annotations

import abc

from blueprints_ng.resources import VmResource, VmResourceConfiguration
from models.base_model import NFVCLBaseModel


class BlueprintNGProviderData(NFVCLBaseModel):
    pass


class BlueprintNGProviderException(Exception):
    pass


class BlueprintNGProviderInterface(abc.ABC):
    data: BlueprintNGProviderData

    @abc.abstractmethod
    def create_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration):
        if not vm_resource_configuration.created:
            raise BlueprintNGProviderException("VM Resource not created")

    @abc.abstractmethod
    def destroy_vm(self):
        pass

    @abc.abstractmethod
    def install_helm_chart(self):
        pass

    @abc.abstractmethod
    def update_values_helm_chart(self):
        pass

    @abc.abstractmethod
    def uninstall_helm_chart(self):
        pass
