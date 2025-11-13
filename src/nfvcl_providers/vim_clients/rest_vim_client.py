from nfvcl_core_models.vim.vim_models import VimModel
from nfvcl_providers.vim_clients.vim_client import VimClient

DEFAULT_PROXMOX_TIMEOUT = 180

class RESTVimClient(VimClient):
    def __init__(self, vim: VimModel):
        super().__init__(vim)

