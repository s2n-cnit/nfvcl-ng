import paramiko
from proxmoxer import ProxmoxAPI

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

        if self.vim.vim_proxmox_token_value:
            self.proxmoxer = ProxmoxAPI(
                self.vim.vim_url,
                user=f'{self.vim.vim_user}@{self.vim.vim_proxmox_realm}',
                token_name=self.vim.vim_proxmox_token_name,
                token_value=self.vim.vim_proxmox_token_value,
                verify_ssl=False,
                timeout=3
            )
        else:
            self.proxmoxer = ProxmoxAPI(
                self.vim.vim_url,
                user=f'{self.vim.vim_user}@{self.vim.vim_proxmox_realm}',
                password=self.vim.vim_password,
                otp=self.vim.vim_proxmox_otp_code if self.vim.vim_proxmox_otp_code else None,
                verify_ssl=False,
                timeout=3
            )

    def close(self):
        self.logger.spam("Closed Proxmox SSH")
        self.ssh_client.close()
