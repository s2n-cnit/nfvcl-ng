import time
from typing import Optional

import paramiko
import semantic_version
from proxmoxer import ProxmoxAPI

from nfvcl_providers.vim_clients.vim_client import VimClient
from nfvcl_core_models.vim.vim_models import VimModel

DEFAULT_PROXMOX_TIMEOUT = 180
IMPORT_URL_VERSION = semantic_version.Version("9.0.17")

class ProxmoxVimClient(VimClient):
    def __init__(self, vim: VimModel):
        super().__init__(vim)
        self.proxmoxer: Optional[ProxmoxAPI] = None
        self.version = None
        self.connect_proxmoxer()
        if self.version < IMPORT_URL_VERSION:
            self._connect_ssh()

    def _connect_ssh(self):
        """Establish SSH connection to Proxmox"""
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(
            self.vim.vim_url,
            port=22,
            username=self.vim.vim_user,
            password=self.vim.vim_password,
            timeout=DEFAULT_PROXMOX_TIMEOUT if self.vim.vim_timeout is None else self.vim.vim_timeout
        )
        self.ssh_client.get_transport().set_keepalive(10)
        self.logger.spam("Connected to Proxmox")

    def connect_proxmoxer(self):
        """Establish Proxmoxer API connection"""
        connection_attempts = 0
        max_retries = 5
        while connection_attempts < max_retries:
            try:
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
                version = self.proxmoxer("version").get()
                self.version = semantic_version.Version(version['version'])
                self.logger.debug(f"Connected to Proxmox API version: {self.version}")
                break
            except Exception as e:
                connection_attempts += 1
                self.logger.error(f"Failed to connect to Proxmox API: {e}. Attempt {connection_attempts} of {max_retries}")
                if connection_attempts >= max_retries:
                    raise ConnectionError("Failed to connect to Proxmox API after multiple attempts")
            time.sleep(3)

    def force_token_refresh(self):
        if not self.vim.proxmox_parameters().proxmox_token_value:
            self.logger.debug("Forcing proxmoxer token refresh")
            self.proxmoxer._backend.auth._get_new_tokens(
                password=self.vim.vim_password,
                otp=self.vim.proxmox_parameters().proxmox_otp_code if self.vim.proxmox_parameters().proxmox_otp_code else None
            )

    def _is_connected(self):
        """Check if SSH client is still connected"""
        try:
            transport = self.ssh_client.get_transport()
            return transport is not None and transport.is_active()
        except:
            return False

    def _reconnect(self):
        """Reconnect SSH client if connection is lost"""
        self.logger.warning("SSH connection lost, attempting to reconnect...")
        try:
            self.ssh_client.close()
        except:
            pass
        self._connect_ssh()

    def exec_command(self, command: str):
        if not self._is_connected():
            self._reconnect()
        return self.ssh_client.exec_command(command)

    def close(self):
        self.logger.spam("Closed Proxmox SSH")
        self.ssh_client.close()
