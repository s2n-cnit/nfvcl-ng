import paramiko
from proxmoxer import ProxmoxAPI

from nfvcl_core.vim_clients.vim_client import VimClient
from nfvcl_core_models.vim.vim_models import VimModel

DEFAULT_PROXMOX_TIMEOUT = 180

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
            timeout=DEFAULT_PROXMOX_TIMEOUT if self.vim.vim_timeout is None else self.vim.vim_timeout
        )
        self.logger.spam("Connected to Proxmox")

        if self.vim.proxmox_parameters().proxmox_token_value:
            self.proxmoxer = ProxmoxAPI(
                self.vim.vim_url,
                user=f'{self.vim.vim_user}@{self.vim.proxmox_parameters().proxmox_realm}',
                token_name=self.vim.proxmox_parameters().proxmox_token_name,
                token_value=self.vim.proxmox_parameters().proxmox_token_value,
                verify_ssl=False,
                timeout=DEFAULT_PROXMOX_TIMEOUT if self.vim.vim_timeout is None else self.vim.vim_timeout
            )
        else:
            self.proxmoxer = ProxmoxAPI(
                self.vim.vim_url,
                user=f'{self.vim.vim_user}@{self.vim.proxmox_parameters().proxmox_realm}',
                password=self.vim.vim_password,
                otp=self.vim.proxmox_parameters().proxmox_otp_code if self.vim.proxmox_parameters().proxmox_otp_code else None,
                verify_ssl=False,
                timeout=DEFAULT_PROXMOX_TIMEOUT if self.vim.vim_timeout is None else self.vim.vim_timeout
            )

    def close(self):
        self.logger.spam("Closed Proxmox SSH")
        self.ssh_client.close()
