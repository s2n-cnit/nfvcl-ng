from __future__ import annotations

import abc
from typing import List, Tuple, Set

from nfvcl_core.providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface, BlueprintNGProviderData
from nfvcl_core_models.resources import VmResource, VmResourceConfiguration, NetResource


class VirtualizationProviderData(BlueprintNGProviderData):
    pass


class VirtualizationProviderException(Exception):
    pass


class VirtualizationProviderInterface(BlueprintNGProviderInterface):
    data: VirtualizationProviderData

    @abc.abstractmethod
    def get_vim_info(self):
        pass

    @abc.abstractmethod
    def create_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        if not vm_resource_configuration.vm_resource.created:
            raise VirtualizationProviderException("VM Resource not created")
        return {}

    @abc.abstractmethod
    def check_networks(self, area: int, networks_to_check: set[str]) -> Tuple[bool, Set[str]]:
        pass

    @abc.abstractmethod
    def attach_nets(self, vm_resource: VmResource, nets_name: List[str]) -> List[str]:
        """
        Attach a network to an already running VM
        DO NOT manually add the network name to the VmResource object

        Args:
            vm_resource: VM where the network will be attached
            nets_name: List of networks to attach

        Returns:
             the ip that has been set in that network
        """
        pass

    @abc.abstractmethod
    def create_net(self, net_resource: NetResource):
        pass

    @abc.abstractmethod
    def destroy_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def reboot_vm(self, vm_resource: VmResource, hard: bool = False):
        pass

    @abc.abstractmethod
    def final_cleanup(self):
        pass
