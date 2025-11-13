import abc
from typing import List, Tuple, Set, Optional, Callable

from nfvcl_core_models.resources import VmResource, VmResourceConfiguration, NetResource, VmStatus
from nfvcl_core_models.vim.vim_models import VimModel
from nfvcl_providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface, BlueprintNGProviderData
from nfvcl_providers.vim_clients.vim_client import VimClient


class VirtualizationProviderData(BlueprintNGProviderData):
    pass


class VirtualizationProviderException(Exception):
    pass


class VirtualizationProviderInterface(BlueprintNGProviderInterface):
    data: VirtualizationProviderData
    vim_client: VimClient
    vim: VimModel

    def __init__(self, area: int, blueprint_id: str, vim_client: VimClient, persistence_function: Optional[Callable] = None):
        self.vim_client = vim_client
        self.vim = vim_client.vim
        super().__init__(area, blueprint_id, persistence_function)

    def get_vim_info(self):
        return self.vim

    @abc.abstractmethod
    def create_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        if not vm_resource_configuration.vm_resource.created:
            raise VirtualizationProviderException("VM Resource not created")
        return {}

    @abc.abstractmethod
    def check_networks(self, networks_to_check: set[str]) -> Tuple[bool, Set[str]]:
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
    def check_vm_status(self, vm_resource: VmResource) -> VmStatus:
        """
        Check the status of a VM
        Args:
            vm_resource: VM to check

        Returns:
            VmStatus containing vm_name, power_status, and ssh_reachable
        """
        pass

    @abc.abstractmethod
    def final_cleanup(self):
        pass
