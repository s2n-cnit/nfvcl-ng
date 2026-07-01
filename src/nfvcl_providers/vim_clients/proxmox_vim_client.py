import re
import time
from pathlib import Path
from time import sleep
from typing import Dict, Optional

import httpx
import paramiko
import proxmoxer
import semantic_version
from proxmoxer import ProxmoxAPI, ResourceException
from pydantic import TypeAdapter

from nfvcl_common.cloudinit_builder import create_cloud_init_iso
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_core_models.vim.vim_models import VimModel
from nfvcl_core_models.vim.vim_models import ProxmoxPrivilegeEscalationTypeEnum
from nfvcl_providers.vim_clients.vim_client import VimClient
from nfvcl_providers.virtualization.proxmox.models.models import ProxmoxZone, Subnet, Vnet, Network

DEFAULT_PROXMOX_API_TIMEOUT = 10
DEFAULT_PROXMOX_VMSTART_TIMEOUT = 180
IMPORT_URL_VERSION = semantic_version.Version("9.0.17")

class ProxmoxVimClient(VimClient):
    def __init__(self, vim: VimModel):
        super().__init__(vim)
        self.proxmoxer: Optional[ProxmoxAPI] = None
        self.version = None
        self.proxmox_node_name: Optional[str] = None
        self.storage_paths: Dict[str, str] = {}
        self.nfvcl_runtime_ready = False
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
            timeout=DEFAULT_PROXMOX_API_TIMEOUT if self.vim.vim_timeout is None else self.vim.vim_timeout
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
                        timeout=DEFAULT_PROXMOX_API_TIMEOUT if self.vim.vim_timeout is None else self.vim.vim_timeout
                    )
                else:
                    self.proxmoxer = ProxmoxAPI(
                        self.vim.vim_url,
                        user=f'{self.vim.vim_user}@{self.vim.proxmox_parameters().proxmox_realm}',
                        password=self.vim.vim_password,
                        otp=self.vim.proxmox_parameters().proxmox_otp_code if self.vim.proxmox_parameters().proxmox_otp_code else None,
                        verify_ssl=False,
                        timeout=DEFAULT_PROXMOX_API_TIMEOUT if self.vim.vim_timeout is None else self.vim.vim_timeout
                    )
                version = self.proxmoxer("version").get()
                self.version = semantic_version.Version(version['version'])
                self.logger.debug(f"Connected to Proxmox API version: {self.version}")
                break
            except Exception as e:
                connection_attempts += 1
                self.logger.error(f"Failed to connect to Proxmox API: {e}. Attempt {connection_attempts} of {max_retries}")
                if connection_attempts >= max_retries:
                    raise ConnectionError("Failed to connect to Proxmox API after multiple attempts") from e
            time.sleep(3)

    def force_token_refresh(self):
        if not self.vim.proxmox_parameters().proxmox_token_value:
            self.logger.debug("Forcing proxmoxer token refresh")
            self.proxmoxer._backend.auth._get_new_tokens(
                password=self.vim.vim_password,
                otp=self.vim.proxmox_parameters().proxmox_otp_code if self.vim.proxmox_parameters().proxmox_otp_code else None
            )

    def get_node_name(self) -> str:
        if self.proxmox_node_name:
            return self.proxmox_node_name

        configured_node = self.vim.proxmox_parameters().proxmox_node
        if configured_node:
            self.proxmox_node_name = configured_node
            return self.proxmox_node_name

        self.proxmox_node_name = self._discover_node_name_by_ip()
        return self.proxmox_node_name

    def get_storage_path(self, storage_id: str) -> str:
        if storage_id not in self.storage_paths:
            self.storage_paths[storage_id] = self._discover_storage_path(storage_id)
        return self.storage_paths[storage_id]

    def _discover_node_name_by_ip(self) -> str:
        nodes = self.proxmoxer("nodes").get()
        for node in nodes:
            node_details = self.proxmoxer(f"nodes/{node['node']}/network").get()
            for interface in node_details:
                if "address" in interface and interface["address"] == self.vim.vim_url:
                    return node["node"]
        raise ValueError(f"Node with ip {self.vim.vim_url} not found")

    def _discover_storage_path(self, storage_id: str) -> str:
        storages = self.proxmoxer("storage").get()
        for item in storages:
            if item["storage"] == storage_id and "iso" in item["content"]:
                return item["path"]
        raise ValueError(f"Storage {storage_id} with ISO content not found")

    @property
    def images_volume(self) -> str:
        return self.vim.proxmox_parameters().proxmox_images_volume

    @property
    def vm_volume(self) -> str:
        return self.vim.proxmox_parameters().proxmox_vm_volume

    @property
    def storage_path(self) -> str:
        return self.get_storage_path(self.images_volume)

    def ensure_nfvcl_runtime_ready(self, script_content: str):
        if self.nfvcl_runtime_ready:
            return
        if self.version < IMPORT_URL_VERSION:
            self._create_ci_qcow_folders()
            self._load_scripts(script_content)
        self.check_storage_content()
        self.nfvcl_runtime_ready = True

    def check_storage_content(self):
        response = self.execute_proxmox_request(
            url=f"nodes/{self.get_node_name()}/storage",
            r_type=HttpRequestType.GET
        )
        for storage in response:
            if storage["storage"] == self.images_volume:
                contents = storage["content"].split(",")
                if all(content in contents for content in ("import", "iso", "snippets")):
                    return
        raise ValueError(f"IMPORT, SNIPPETS and ISO must be enable on storage {self.images_volume}")

    def patch_vm_config(self, node: str, vmid: int, new_config: dict):
        self.execute_proxmox_request(
            url=f"nodes/{node}/qemu/{vmid}/config",
            r_type=HttpRequestType.PUT,
            parameters=new_config
        )

    def create_vm(self, vm_to_create: dict):
        self.execute_proxmox_request(
            url=f"nodes/{self.get_node_name()}/qemu",
            parameters=vm_to_create,
            r_type=HttpRequestType.POST,
            node_name=self.get_node_name()
        )

    def start_vm(self, vmid: int | str):
        self.execute_proxmox_request(
            url=f"nodes/{self.get_node_name()}/qemu/{vmid}/status/start",
            node_name=self.get_node_name(),
            r_type=HttpRequestType.POST
        )

    def reboot_vm(self, vmid: int | str, hard: bool = False):
        reboot_type = "reset" if hard else "reboot"
        self.logger.debug(f"{'Hard' if hard else 'Soft'} restarting VM {vmid}")
        self.execute_proxmox_request(
            url=f"nodes/{self.get_node_name()}/qemu/{vmid}/status/{reboot_type}",
            node_name=self.get_node_name(),
            r_type=HttpRequestType.POST
        )

    def get_vm_status(self, vmid: int | str):
        return self.execute_proxmox_request(
            url=f"nodes/{self.get_node_name()}/qemu/{vmid}/status/current",
            r_type=HttpRequestType.GET
        )

    def attach_vm_net(self, vmid: int | str, interface: str, bridge: str):
        self.execute_proxmox_request(
            url=f"nodes/{self.get_node_name()}/qemu/{vmid}/config",
            parameters={interface: f"virtio,bridge={bridge},firewall=0"},
            r_type=HttpRequestType.PUT
        )

    def upload_cnit_iso(self, meta, user, vendor, network, filename):
        file_content, checksum = create_cloud_init_iso(
            meta_data=meta,
            user_data=user,
            vendor_data=vendor,
            network_config=network
        )
        file = Path(f"/tmp/{filename}.iso")
        with open(file, "wb") as f:
            f.write(file_content.getbuffer())
        with open(file, "rb") as f:
            self.execute_proxmox_request(
                url=f"nodes/{self.get_node_name()}/storage/{self.images_volume}/upload",
                r_type=HttpRequestType.POST,
                parameters={"content": "iso", "filename": f},
                node_name=self.get_node_name()
            )
        file.unlink()

    def delete_volume(self, node: str, storage: str, content: str, file_name: str):
        self.execute_proxmox_request(
            url=f"/nodes/{node}/storage/{storage}/content/{content}/{file_name}",
            r_type=HttpRequestType.DELETE
        )

    def delete_vm(self, vmid: int | str, resource_group: str):
        vmid = str(vmid)
        self.logger.debug(f"Stopping VM {vmid}")
        self.execute_proxmox_request(
            url=f"nodes/{self.get_node_name()}/qemu/{vmid}/status/stop",
            node_name=self.get_node_name(),
            r_type=HttpRequestType.POST
        )
        self.logger.debug(f"Destroying VM {vmid}")
        self.execute_proxmox_request(
            url=f"nodes/{self.get_node_name()}/qemu/{vmid}",
            parameters={"purge": 1},
            node_name=self.get_node_name(),
            r_type=HttpRequestType.DELETE
        )
        if self.version >= IMPORT_URL_VERSION:
            self.delete_volume(
                node=self.get_node_name(),
                storage=self.images_volume,
                content="local:iso",
                file_name=f"{vmid}_{resource_group}.iso"
            )
        else:
            self.execute_ssh_command(f"rm {self.storage_path}/snippets/user_cloud_init_{vmid}_{resource_group}.yaml")
            self.execute_ssh_command(f"rm {self.storage_path}/snippets/network_cloud_init_{vmid}_{resource_group}.yaml")
        self.logger.success(f"VM {vmid} destroyed")

    def get_permission(self):
        return self.execute_proxmox_request(
            url="/access/acl",
            r_type=HttpRequestType.GET
        )

    def get_groups(self):
        groups = self.execute_proxmox_request(
            url="/access/groups",
            r_type=HttpRequestType.GET
        )
        user = f"{self.vim.vim_user}@{self.vim.proxmox_parameters().proxmox_realm}"
        return [g["groupid"] for g in groups if user in g.get("users", [])]

    def get_pools(self):
        user_pools = []
        user = f"{self.vim.vim_user}@{self.vim.proxmox_parameters().proxmox_realm}"
        group_list = self.get_groups()
        acl_list = self.get_permission()
        for acl in acl_list:
            path = acl["path"]
            if path.startswith("/pool/"):
                poolid = path.split("/pool/")[1]

                if user in acl.get("ugid", []):
                    user_pools.append(poolid)

                for g in group_list:
                    if g in acl.get("ugid", []):
                        user_pools.append(poolid)
        return list(set(user_pools))

    def pre_creation_check(self, networks: list[str]):
        response = self.execute_proxmox_request(
            url="cluster/sdn/vnets",
            r_type=HttpRequestType.GET
        )
        ta = TypeAdapter(list[Vnet])
        vnets = ta.validate_python(response)

        # Check if subnet has gateway set, no gateway = DHCP doesn't work in proxmox.
        for vnet in vnets:
            if vnet.vnet in networks:
                response = self.execute_proxmox_request(
                    url=f"cluster/sdn/vnets/{vnet.vnet}/subnets",
                    r_type=HttpRequestType.GET
                )
                ta = TypeAdapter(list[Subnet])
                subnets = ta.validate_python(response)
                if len(subnets) == 1:
                    if subnets[0].gateway is None:
                        raise ValueError(f"Error Subnet of Vnet {vnet.vnet} has no gateway defined")
                else:
                    raise ValueError(f"Error Vnet {vnet.vnet} has no subnets or more than 1 subnet")

        if self.vim.proxmox_parameters().proxmox_resource_pool:
            pools = self.get_pools()
            if self.vim.proxmox_parameters().proxmox_resource_pool not in pools:
                raise ValueError(f"Error Pool {self.vim.proxmox_parameters().proxmox_resource_pool} does not exist or you do not have access to it")

    def get_free_vmid(self) -> int:
        nfvcl_vmid = list(range(10000, 11000))
        for _id in nfvcl_vmid:
            try:
                response = self.execute_proxmox_request(
                    url="cluster/nextid",
                    parameters={"vmid": _id},
                    r_type=HttpRequestType.GET,
                    logger=False
                )
                if response == str(_id):
                    return _id
            except ResourceException as e:
                self.logger.debug(f"Proxmox VMID {_id} is not available: {e}")
        raise ValueError("No free vmid available")

    def _create_ci_qcow_folders(self):
        self.execute_ssh_command(f'mkdir -p {self.storage_path}/snippets')
        self.execute_ssh_command(f'mkdir -p {self.storage_path}/images/0')
        self.execute_ssh_command('mkdir -p /root/scripts')

    def _load_scripts(self, script_content: str):
        self.execute_ssh_command(f"echo '{script_content}' > /root/scripts/image_script.sh")
        self.execute_ssh_command("chmod +x /root/scripts/image_script.sh")

    def load_cloud_init(self, cloud_init: str, cloud_init_path: str):
        self.execute_ssh_command(f"echo '{cloud_init}' > {cloud_init_path}")

    def download_cloud_image(self, image_url: str, image_name: str):
        # TODO seems to be supported on 9.x: https://bugzilla.proxmox.com/show_bug.cgi?id=2424
        if self.version >= IMPORT_URL_VERSION:
            response = httpx.get(f"{image_url}.SHA256SUM")
            checksum = response.content.split()[0]
            download_args = {"url": image_url, "content": "import", "filename": f"{image_name}.qcow2", "checksum": checksum, "checksum-algorithm": "sha256"}
            self.execute_proxmox_request(
                url=f"nodes/{self.get_node_name()}/storage/{self.images_volume}/download-url",
                r_type=HttpRequestType.POST,
                node_name=self.get_node_name(),
                parameters=download_args
            )
        else:
            self.execute_ssh_command(f'/root/scripts/image_script.sh {image_url} {self.storage_path}/images/0/{image_name}.qcow2')

    def get_vm_config(self, vmid: int):
        return self.execute_proxmox_request(
            url=f"nodes/{self.get_node_name()}/qemu/{vmid}/config",
            r_type=HttpRequestType.GET
        )

    def get_qemu_agent_interfaces(self, vmid: int):
        return self.execute_proxmox_request(
            url=f"nodes/{self.get_node_name()}/qemu/{vmid}/agent/network-get-interfaces",
            r_type=HttpRequestType.GET
        )

    def get_disks_size(self, vmid: int):
        config = self.get_vm_config(vmid)
        disks = list(filter(lambda x: re.match('scsi[0-9]+', x), config.keys()))
        if disks is not None:
            disks_memory = list()
            for disk in disks:
                size: str = config[disk].split("size=")[1]  # 10G or 10M
                if size:
                    disks_memory.append((size, disk))
                else:
                    raise ValueError(f"Disk size unit not supported: {size}")
            return disks_memory
        else:
            raise ValueError(f"Non disk devices found for VM-ID: {vmid}")

    def resize_disk(self, vmid: int, desired_size: int, disk: str):
        disks = self.get_disks_size(vmid)
        desired_size = desired_size * 1024
        for d in disks:
            if d[1] == disk:
                if "M" in d[0]:
                    size = int(d[0].split("M")[0])
                else:
                    size = int(d[0].split("G")[0]) * 1024
                if desired_size > size:
                    size_to_add = desired_size - size
                    self.execute_proxmox_request(
                        url=f"nodes/{self.get_node_name()}/qemu/{vmid}/resize",
                        parameters={
                            "disk": f"{d[1]}",
                            "size": f"+{size_to_add}M"
                        },
                        node_name=self.get_node_name(),
                        r_type=HttpRequestType.PUT
                    )
                else:
                    self.logger.warning(f"Disk of VM: {vmid}, is already larger than the desired size")

    def qemu_guest_agent_ready(self, vmid: int):
        self.logger.info("Waiting qemu guest agent")
        exit_status = 1
        timeout = time.time() + (DEFAULT_PROXMOX_VMSTART_TIMEOUT if self.vim.vim_timeout is None else self.vim.vim_timeout)
        while exit_status != 0 and time.time() < timeout:
            try:
                response = self.execute_proxmox_request(
                    url=f"nodes/{self.get_node_name()}/qemu/{vmid}/agent/ping",
                    r_type=HttpRequestType.POST,
                    logger=False
                )
                if response is not None:
                    exit_status = 0
                    return
            except Exception as e:
                self.logger.debug(f"Waiting qemu guest agent... ({e})")
                sleep(3)
        raise ValueError("Timeout waiting for qemu guest agent")

    def get_nfvcl_sdn_zone(self) -> ProxmoxZone:
        response = self.execute_proxmox_request(
            url="cluster/sdn/zones",
            r_type=HttpRequestType.GET
        )
        ta = TypeAdapter(list[ProxmoxZone])
        zones = ta.validate_python(response)
        for zone in zones:
            if zone.zone == self.vim.proxmox_parameters().proxmox_sdn_zone:
                return zone
        raise ValueError("NFVCL sdn zone not found, you must create a zone called 'nfvcl' with DHCP enabled (case sensitive)")

    def apply_sdn(self):
        self.logger.info("Applying sdn configuration")
        self.execute_proxmox_request(
            url="cluster/sdn",
            node_name=self.get_node_name(),
            r_type=HttpRequestType.PUT
        )

    def create_sdn_vnet(self, identifier: str, alias: str):
        nfvcl_zone = self.get_nfvcl_sdn_zone()
        self.execute_proxmox_request(
            url='cluster/sdn/vnets',
            r_type=HttpRequestType.POST,
            parameters={'vnet': identifier, 'zone': nfvcl_zone.zone, 'alias': alias}
        )
        self.apply_sdn()

    def delete_sdn_vnet(self, vnet_id: str):
        tmp = self.execute_proxmox_request(
            url=f"cluster/sdn/vnets/{vnet_id}/subnets",
            r_type=HttpRequestType.GET
        )
        ta = TypeAdapter(list[Subnet])
        subnets = ta.validate_python(tmp)
        for subnet in subnets:
            self.logger.info(f"Deleting vnet subnet: {subnet.id}")
            self.delete_sdn_subnet(subnet)
        self.execute_proxmox_request(
            url=f"/cluster/sdn/vnets/{vnet_id}",
            r_type=HttpRequestType.DELETE
        )
        self.apply_sdn()

    def create_sdn_subnet(self, vnet_id: str, cidr: str, start_dhcp: str, end_dhcp: str, gateway: str):
        self.execute_proxmox_request(
            url=f"cluster/sdn/vnets/{vnet_id}/subnets",
            r_type=HttpRequestType.POST,
            parameters={
                'subnet': cidr,
                'type': 'subnet',
                'gateway': gateway,
                'dhcp-range': f'start-address={start_dhcp},end-address={end_dhcp}'
            }
        )
        self.apply_sdn()

    def delete_sdn_subnet(self, subnet: Subnet):
        self.execute_proxmox_request(
            url=f'/cluster/sdn/vnets/{subnet.vnet}/subnets/{subnet.id}',
            r_type=HttpRequestType.DELETE
        )
        self.apply_sdn()
        self.logger.success(f"Subnet {subnet.id} deleted")

    def check_networks(self, networks_to_check: set[str]):
        networks = set()
        network_tmp = self.execute_proxmox_request(
            url=f'nodes/{self.get_node_name()}/network',
            r_type=HttpRequestType.GET,
        )
        ta = TypeAdapter(list[Network])
        networks_tmp = ta.validate_python(network_tmp)
        for net in networks_tmp:
            if net.address:
                networks.add(net.iface)

        vnet_tmp = self.execute_proxmox_request(
            url='/cluster/sdn/vnets',
            r_type=HttpRequestType.GET,
        )
        ta = TypeAdapter(list[Vnet])
        vnets = ta.validate_python(vnet_tmp)

        for vnet in vnets:
            if vnet.zone == self.vim.proxmox_parameters().proxmox_sdn_zone:
                networks.add(vnet.vnet)

        return networks_to_check.issubset(networks), networks_to_check.difference(networks)

    def _is_connected(self):
        """Check if SSH client is still connected"""
        try:
            transport = self.ssh_client.get_transport()
            return transport is not None and transport.is_active()
        except Exception:
            return False

    def _reconnect(self):
        """Reconnect SSH client if connection is lost"""
        self.logger.warning("SSH connection lost, attempting to reconnect...")
        try:
            self.ssh_client.close()
        except Exception:
            pass
        self._connect_ssh()

    def exec_command(self, command: str):
        if not hasattr(self, "ssh_client"):
            raise RuntimeError("Proxmox SSH connection is not initialized for this VIM client")
        if not self._is_connected():
            self._reconnect()
        return self.ssh_client.exec_command(command)

    def execute_ssh_command(self, command: str):
        if self.vim.proxmox_parameters().proxmox_privilege_escalation == ProxmoxPrivilegeEscalationTypeEnum.SUDO_WITHOUT_PASSWORD:
            # Needed to escape single quotes: https://stackoverflow.com/a/1250279
            command = command.replace("'", """'"'"'""")
            command = f"sudo sh -c '{command}'"
        stdin, stdout, stderr = self.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            raise RuntimeError(f"Error executing command: {command}")
        return stdout

    def execute_proxmox_request(self, url: str, r_type: HttpRequestType, node_name=None, parameters=None, logger=True):
        connection_attempts = 0
        max_retries = 5
        while connection_attempts < max_retries:
            try:
                match r_type:
                    case HttpRequestType.GET:
                        response = self.proxmoxer(url).get(**parameters if parameters else {})
                    case HttpRequestType.POST:
                        response = self.proxmoxer(url).post(**parameters if parameters else {})
                    case HttpRequestType.PUT:
                        response = self.proxmoxer(url).put(**parameters if parameters else {})
                    case HttpRequestType.DELETE:
                        response = self.proxmoxer(url).delete(**parameters if parameters else {})
                    case _:
                        raise RuntimeError("Api request type not supported")

                if node_name:
                    data = {"status": ""}
                    exit_status = ""
                    while data["status"] != "stopped":
                        output = f"{response.split(':')[5]}, VMid {response.split(':')[6]}" if response.split(':')[6] else f"{response.split(':')[5]}"
                        self.logger.debug(f"Waiting for task: {output}")
                        data = self.proxmoxer(f"nodes/{node_name}/tasks/{response}/status").get()
                        if data["status"] == "stopped":
                            exit_status = data["exitstatus"]
                        sleep(3)
                    if exit_status != "OK":
                        raise RuntimeError(f"{exit_status}")
                return response
            except (proxmoxer.core.AuthenticationError, proxmoxer.core.ResourceException) as e:
                if isinstance(e, proxmoxer.core.ResourceException) and not e.status_code == 401:
                    if logger:
                        self.logger.error(f"{e}")
                    raise
                connection_attempts += 1
                self.logger.error(f"Error executing Proxmox request: {e}, attempt {connection_attempts}/{max_retries}")
                self.logger.debug("Forcing proxmox client to re-authenticate")
                self.force_token_refresh()
                if connection_attempts >= max_retries:
                    raise RuntimeError(f"Failed to execute Proxmox request after {max_retries} attempts") from e
                sleep(2)
        return None

    def close(self):
        if self.closed:
            return
        ssh_client = getattr(self, "ssh_client", None)
        if ssh_client is not None:
            self.logger.spam("Closed Proxmox SSH")
            ssh_client.close()
        super().close()
