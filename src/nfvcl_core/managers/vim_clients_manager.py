from typing import Dict, cast

from nfvcl_core.managers import TopologyManager
from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core_models.vim.vim_models import VimTypeEnum
from nfvcl_providers.vim_clients.openstack_vim_client import OpenStackVimClient
from nfvcl_providers.vim_clients.proxmox_vim_client import ProxmoxVimClient
from nfvcl_providers.vim_clients.vim_client import VimClient


class VimClientsManager(GenericManager):
    def __init__(self, topology_manager: TopologyManager):
        super().__init__()
        self._topology_manager = topology_manager
        self.clients: Dict[str, VimClient] = {}

    def get_vim_client(self, requester: object, vim_type: VimTypeEnum, vim_name: str) -> VimClient:
        if vim_type == VimTypeEnum.PROXMOX:
            return self.get_proxmox_client(requester, vim_name)
        elif vim_type == VimTypeEnum.OPENSTACK:
            return self.get_openstack_client(requester, vim_name)
        else:
            raise ValueError(f"Unknown VIM type {vim_type}")

    def get_proxmox_client(self, requester: object, vim_name: str) -> ProxmoxVimClient:
        return cast(ProxmoxVimClient, self._get_client(requester, vim_name, ProxmoxVimClient))

    def get_openstack_client(self, requester: object, vim_name: str) -> OpenStackVimClient:
        return cast(OpenStackVimClient, self._get_client(requester, vim_name, OpenStackVimClient))

    def _get_client(self, requester: object, vim_name: str, vim_type: type) -> VimClient:
        self.logger.spam(f"Getting {vim_type.__name__} for requester {requester.__class__.__name__} and VIM {vim_name}")
        if vim_name not in self.clients:
            self.logger.info(f"Creating new {vim_type.__name__} for vim {vim_name}")
            self.clients[vim_name] = vim_type(self._topology_manager.get_vim(vim_name))
        client = self.clients[vim_name]
        requester_id = id(requester)
        if requester_id not in client.references:
            client.references.append(requester_id)

        return cast(VimClient, client)

    def release_client(self, requester: object, vim_name: str):
        self.logger.spam(f"Releasing VIM client for requester {requester.__class__.__name__} and VIM {vim_name}")
        client = self.clients[vim_name]
        requester_id = id(requester)
        if requester_id in client.references:
            self.logger.spam(f"Removing reference to object {requester_id} from VIM {vim_name} client")
            client.references.remove(requester_id)
        else:
            raise ValueError(f"Requester {requester} does not have a client for VIM {vim_name}")
        if len(client.references) == 0:
            self.logger.spam(f"No more references to VIM {vim_name} client, closing")
            client.close()
            del self.clients[vim_name]
