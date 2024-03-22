from __future__ import annotations

import abc

from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface, \
    BlueprintNGProviderData
from blueprints_ng.resources import VmResource, VmResourceConfiguration


class VirtualizationProviderData(BlueprintNGProviderData):
    pass


class VirtualizationProviderException(Exception):
    pass


class VirtualizationProviderInterface(BlueprintNGProviderInterface):
    data: VirtualizationProviderData

    @abc.abstractmethod
    def create_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        if not vm_resource_configuration.vm_resource.created:
            raise VirtualizationProviderException("VM Resource not created")
        return {}

    @abc.abstractmethod
    def destroy_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def final_cleanup(self):
        pass
