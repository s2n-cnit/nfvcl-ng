import abc
from typing import List, Tuple, Set, Optional, Callable

from nfvcl_core_models.providers.providers import ProviderData, ProviderException
from nfvcl_core_models.resources import VmResource, VmResourceConfiguration, NetResource, VmStatus
from nfvcl_core_models.vim.vim_models import VimModel, VimTypeEnum
from nfvcl_providers.provider_interface import ProviderInterface
from nfvcl_providers.vim_clients.vim_client import VimClient
from nfvcl_providers.vim_clients.vim_context import VimClientPool, VimModelResolver


class VirtualizationProviderData(ProviderData):
    pass


class VirtualizationProviderException(ProviderException):
    pass


class VirtualizationProviderInterface(ProviderInterface):
    data: VirtualizationProviderData
    provider_vim_type: VimTypeEnum

    def __init__(
        self,
        vim_client_pool: Optional[VimClientPool] = None,
        vim_model_resolver: Optional[VimModelResolver] = None,
        persistence_function: Optional[Callable] = None,
    ):
        # The VimClientPool is constructed in the ProviderManager; this fallback is to use the provider externally
        if vim_client_pool is None:
            if vim_model_resolver is not None:
                vim_client_pool = VimClientPool(vim_model_resolver)
            else:
                raise ValueError("A VimClientPool or VimModelResolver must be provided")
        self.vim_client_pool = vim_client_pool
        super().__init__(persistence_function)

    def get_vim_client(self, area: int) -> VimClient:
        return self.vim_client_pool.get_client(area, self.provider_vim_type)

    def get_vim_info(self, area: int) -> VimModel:
        return self.vim_client_pool.get_vim(area, self.provider_vim_type)

    @abc.abstractmethod
    def create_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        if not vm_resource_configuration.vm_resource.created:
            raise VirtualizationProviderException("VM Resource not created")
        return {}

    @abc.abstractmethod
    def check_networks_exist_on_vim(self, area: int, networks_to_check: set[str], resource_group: Optional[str] = None) -> Tuple[bool, Set[str]]:
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
    def cleanup_resource_group(self, resource_group: str):
        pass
