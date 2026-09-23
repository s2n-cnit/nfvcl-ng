import abc
from typing import List, Tuple, Set, Optional, Callable

from nfvcl_core_models.providers.providers import ProviderData, ProviderException
from nfvcl_core_models.resources import ContainerResource, ContainerStatus, LXCContainerResource, NetResource
from nfvcl_core_models.vim.vim_models import VimModel, VimTypeEnum
from nfvcl_providers.provider_interface import ProviderInterface
from nfvcl_providers.vim_clients.vim_client import VimClient
from nfvcl_providers.vim_clients.vim_context import VimClientPool, VimModelResolver


class ContainerizationProviderData(ProviderData):
    pass


class ContainerizationProviderException(ProviderException):
    pass


class ContainerizationProviderInterface(ProviderInterface):
    data: ContainerizationProviderData
    provider_vim_type: VimTypeEnum

    def __init__(
        self,
        vim_client_pool: Optional[VimClientPool] = None,
        vim_model_resolver: Optional[VimModelResolver] = None,
        persistence_function: Optional[Callable] = None,
    ):
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
    def create_container(self, container_resource: ContainerResource):
        pass

    @abc.abstractmethod
    def check_networks_exist(self, area: int, networks_to_check: set[str], resource_group: Optional[str] = None) -> Tuple[bool, Set[str]]:
        pass

    @abc.abstractmethod
    def attach_nets(self, container_resource: ContainerResource, nets_name: List[str]) -> List[str]:
        pass

    @abc.abstractmethod
    def create_net(self, net_resource: NetResource):
        pass

    @abc.abstractmethod
    def destroy_container(self, container_resource: ContainerResource):
        pass

    @abc.abstractmethod
    def reboot_container(self, container_resource: ContainerResource, hard: bool = False):
        pass

    @abc.abstractmethod
    def check_container_status(self, container_resource: ContainerResource) -> ContainerStatus:
        pass

    @abc.abstractmethod
    def get_container_interface_name_from_parent(self, container_resource: LXCContainerResource, parent_interface: str) -> Optional[str]:
        """
        Resolve the container-side interface name attached to a given parent interface.

        Args:
            container_resource: The container whose interfaces are examined.
            parent_interface: Name of the host-side interface/network.

        Returns:
            The interface name as seen inside the container, or ``None`` if not found.
        """
        pass

    @abc.abstractmethod
    def cleanup_resource_group(self, resource_group: str):
        pass
