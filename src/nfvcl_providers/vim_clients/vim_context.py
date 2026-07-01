from __future__ import annotations

from threading import Lock
from typing import Protocol

from nfvcl_common.utils.log import create_logger
from nfvcl_core_models.vim.vim_models import VimModel, VimTypeEnum
from nfvcl_providers.vim_clients.vim_client import VimClient


class VimModelResolver(Protocol):
    def get_vim_by_area(self, area: int) -> VimModel:
        ...

    def get_vim_by_name(self, vim_name: str) -> VimModel:
        ...


def get_vim_client_class(vim_type: VimTypeEnum) -> type[VimClient]:
    match vim_type:
        case VimTypeEnum.OPENSTACK:
            from nfvcl_providers.vim_clients.openstack_vim_client import OpenStackVimClient

            return OpenStackVimClient
        case VimTypeEnum.PROXMOX:
            from nfvcl_providers.vim_clients.proxmox_vim_client import ProxmoxVimClient

            return ProxmoxVimClient
        case VimTypeEnum.EXTERNAL_REST:
            from nfvcl_providers.vim_clients.rest_vim_client import RESTVimClient

            return RESTVimClient
        case _:
            raise KeyError(vim_type)


class VimClientPool:
    def __init__(
        self,
        vim_model_resolver: VimModelResolver,
        initial_clients: dict[str, VimClient] | None = None,
    ):
        self.logger = create_logger(self.__class__.__name__)
        self.vim_model_resolver = vim_model_resolver
        self.clients: dict[str, VimClient] = initial_clients or {}
        self._lock = Lock()

    def get_vim(self, area: int, expected_type: VimTypeEnum) -> VimModel:
        vim = self.vim_model_resolver.get_vim_by_area(area)
        if vim.vim_type != expected_type:
            raise ValueError(f"Area {area} is backed by VIM type {vim.vim_type}, expected {expected_type}")
        return vim

    def get_vim_by_name(self, vim_name: str, expected_type: VimTypeEnum) -> VimModel:
        vim = self.vim_model_resolver.get_vim_by_name(vim_name)
        if vim.vim_type != expected_type:
            raise ValueError(f"VIM {vim_name} has type {vim.vim_type}, expected {expected_type}")
        return vim

    def _get_client_for_vim(self, vim: VimModel) -> VimClient:
        with self._lock:
            if vim.name not in self.clients:
                client_class = get_vim_client_class(vim.vim_type)
                self.logger.verbose(f"Creating new client for VIM {vim.name}")
                self.clients[vim.name] = client_class(vim)
            return self.clients[vim.name]

    def get_client(self, area: int, expected_type: VimTypeEnum) -> VimClient:
        return self._get_client_for_vim(self.get_vim(area, expected_type))

    def get_client_by_vim_name(self, vim_name: str, expected_type: VimTypeEnum) -> VimClient:
        return self._get_client_for_vim(self.get_vim_by_name(vim_name, expected_type))

    def close(self) -> None:
        for client in self.clients.values():
            client.close()
        self.clients.clear()
