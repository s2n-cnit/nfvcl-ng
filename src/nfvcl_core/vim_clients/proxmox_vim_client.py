import paramiko

from nfvcl_core.vim_clients.vim_client import VimClient
from nfvcl_core_models.vim.vim_models import VimModel


class ProxmoxVimClient(VimClient):
    def __init__(self, vim: VimModel):
        super().__init__(vim)
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(
            self.vim.vim_url,
            port=22,
            username=self.vim.vim_user,
            password=self.vim.vim_password,
            timeout=3
        )
        self.logger.spam("Connected to Proxmox")

    def close(self):
        self.logger.spam("Closed Proxmox SSH")
        self.ssh_client.close()
