from __future__ import annotations

import abc

from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface, \
    BlueprintNGProviderData
from blueprints_ng.resources import VmResource, VmResourceConfiguration, NetResource


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
    def attach_net(self, vm_resource: VmResource, net_name: str):
        """
        Attach a network to an already running VM
        DO NOT manually add the network name to the VmResource object

        Args:
            vm_resource: VM where the network will be attached
            net_name: Network to attach
        """
        pass

    @abc.abstractmethod
    def create_net(self, net_resource: NetResource):
        pass

    @abc.abstractmethod
    def destroy_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def final_cleanup(self):
        pass
