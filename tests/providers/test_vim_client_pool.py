from nfvcl_core_models.vim.vim_models import VimModel, VimTypeEnum
from nfvcl_providers.vim_clients import vim_context
from nfvcl_providers.vim_clients.vim_client import VimClient
from tests.providers.fakes import build_vim


class MutableVimResolver:
    def __init__(self, vim: VimModel):
        self.vim = vim

    def get_vim_by_area(self, area: int) -> VimModel:
        if area not in self.vim.areas:
            raise ValueError(f"Unexpected area {area}")
        return self.vim

    def get_vim_by_name(self, vim_name: str) -> VimModel:
        if vim_name != self.vim.name:
            raise ValueError(f"Unexpected VIM {vim_name}")
        return self.vim


class FakeVimClient(VimClient):
    def __init__(self, vim: VimModel):
        super().__init__(vim)
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        super().close()


def test_vim_client_pool_refreshes_client_when_vim_model_changes(monkeypatch):
    monkeypatch.setattr(vim_context, "get_vim_client_class", lambda vim_type: FakeVimClient)

    vim = build_vim("vim_a", VimTypeEnum.OPENSTACK, area=1)
    resolver = MutableVimResolver(vim)
    pool = vim_context.VimClientPool(resolver)

    old_client = pool.get_client(1, VimTypeEnum.OPENSTACK)
    assert pool.get_client(1, VimTypeEnum.OPENSTACK) is old_client

    resolver.vim = vim.model_copy(deep=True, update={"ssh_keys": ["ssh-rsa updated-key"]})
    new_client = pool.get_client(1, VimTypeEnum.OPENSTACK)

    assert new_client is not old_client
    assert old_client.closed is True
    assert old_client.close_calls == 1
    assert new_client.vim.ssh_keys == ["ssh-rsa updated-key"]
    assert pool.clients[vim.name] is new_client
