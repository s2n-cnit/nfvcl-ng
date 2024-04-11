import time
import math
from pathlib import Path
from typing import Dict

from blueprints_ng.cloudinit_builder import CloudInit
from blueprints_ng.providers.configurators.ansible_utils import run_ansible_playbook
from blueprints_ng.resources import VmResource, VmResourceConfiguration, VmResourceNetworkInterfaceAddress, VmResourceNetworkInterface, VmResourceAnsibleConfiguration, NetResource
import paramiko
import json

from blueprints_ng.providers.virtualization.virtualization_provider_interface import VirtualizationProviderException, \
    VirtualizationProviderInterface, VirtualizationProviderData
from blueprints_ng.utils import rel_path

cloud_init_packages = ['qemu-guest-agent']
cloud_init_runcmd = ["systemctl enable qemu-guest-agent.service", "systemctl start qemu-guest-agent.service"]

class VirtualizationProviderDataProxmox(VirtualizationProviderData):
    proxmox_dict: Dict[str, str] = {}


class VirtualizationProviderProxmoxException(VirtualizationProviderException):
    pass


class VirtualizationProviderProxmox(VirtualizationProviderInterface):
    def create_net(self, net_resource: NetResource):
        pass

    def init(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.data: VirtualizationProviderDataProxmox = VirtualizationProviderDataProxmox()
        self.vim = self.topology.get_vim_from_area_id_model(self.area)
        self.ssh.connect(self.vim.vim_url, port=22, username=self.vim.vim_user,
                         password=self.vim.vim_password, timeout=3)
        self.path = self.__get_storage_path(self.vim.vim_proxmox_storage_id)

        self.__create_ci_qcow_folders()
        self.__load_scripts()

    def create_vm(self, vm_resource: VmResource):
        self.logger.info(f"Creating VM {vm_resource.name}")
        self.__download_cloud_image(f'{vm_resource.image.url}', f'{vm_resource.image.name}')
        cloud_init = CloudInit(password=vm_resource.password,
                               packages=cloud_init_packages,
                               ssh_authorized_keys=self.vim.ssh_keys,
                               runcmd=cloud_init_runcmd).build_cloud_config()
        vmid = self.__get_free_vmid()
        cloud_init_files_path = f"{self.path}/snippets/cloud_init_{vmid}_{self.blueprint.id}.yaml"
        self.__load_cloud_init(cloud_init=cloud_init, cloud_init_path=cloud_init_files_path)
        self.__execute_ssh_command(f'qm create {vmid} --agent 1 --memory {vm_resource.flavor.memory_mb} --name {vm_resource.get_name_k8s_format()} --cores {vm_resource.flavor.vcpu_count} --sockets 1 --cpu {vm_resource.flavor.vcpu_type} --net0 virtio,bridge={vm_resource.management_network},firewall=0 --scsihw virtio-scsi-pci')
        self.data.proxmox_dict[vm_resource.id] = str(vmid)
        self.blueprint.to_db()
        self.__execute_ssh_command(f'qm importdisk {vmid} {self.path}/template/qcow/{vm_resource.image.name}.qcow2 {self.vim.vim_proxmox_storage_volume}')
        self.__execute_ssh_command(f'qm set {vmid} --scsi0 {self.vim.vim_proxmox_storage_volume}:vm-{vmid}-disk-0,discard=on,iothread=on,cache=writethrough')
        self.resize_disk(vmid, int(vm_resource.flavor.storage_gb))
        self.__execute_ssh_command(f'qm set {vmid} --ide2 {self.vim.vim_proxmox_storage_volume}:cloudinit')
        self.__execute_ssh_command(f"qm set {vmid} --boot order=scsi0")
        self.__execute_ssh_command(f'qm set {vmid} --cicustom "user=local:snippets/cloud_init_{vmid}_{self.blueprint.id}.yaml"')
        self.__execute_ssh_command(f'qm set {vmid} --ipconfig0 ip=dhcp')

        self.blueprint.to_db()

        # Getting detailed info about the networks attached to the machine
        self.__execute_ssh_command(f"qm start {vmid}")

        # Loop until qemu-agent is ready
        self.qemu_guest_agent_ready(vmid)
        self.__parse_proxmox_addresses(vm_resource, vmid)

        # Find the IP to use for configuring the VMte
        if vm_resource.management_network in vm_resource.network_interfaces.keys() and len(vm_resource.network_interfaces[vm_resource.management_network].fixed.ip) > 0:
            vm_resource.access_ip = vm_resource.network_interfaces[vm_resource.management_network].fixed.ip
        else:
            raise VirtualizationProviderProxmoxException(f"Error {vm_resource.name} has no an IP assigned")

        # The VM is now created
        vm_resource.created = True

        self.logger.success(f"Creating VM {vm_resource.name} finished")
        self.blueprint.to_db()

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        # # The parent method checks if the resource is created and throw an exception if not
        # super().configure_vm(vm_resource_configuration)
        # self.logger.info(f"Configuring VM {vm_resource_configuration.vm_resource.name}")
        #
        # configurator_facts = None
        #
        # # Different handlers for different configuration types
        # if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):  # VmResourceNativeConfiguration
        #     configurator_facts = self.__configure_vm_ansible(vm_resource_configuration)
        #
        # self.logger.success(f"Configuring VM {vm_resource_configuration.vm_resource.name} finished")
        # self.blueprint.to_db()
        #
        # return configurator_facts
        pass

    def destroy_vm(self, vm_resource: VmResource):
        vmid = self.data.proxmox_dict[vm_resource.id]
        self.__execute_ssh_command(f"qm stop {vmid}")
        self.__execute_ssh_command(f"qm destroy {vmid} --purge 1 --destroy-unreferenced-disks 1")
        self.__execute_ssh_command(f"rm {self.path}/snippets/cloud_init_{vmid}_{self.blueprint.id}.yaml")
        del self.data.proxmox_dict[vm_resource.id]

    def final_cleanup(self):
        pass

    def __get_free_vmid(self) -> int:
        nfvcl_vmid = list(range(10000, 11000))
        stdout = self.__execute_ssh_command('pvesh get /cluster/resources --type vm --output-format json')
        vms = json.loads(stdout.readline())
        for item in vms:
            if item['vmid'] in nfvcl_vmid:
                nfvcl_vmid.remove(item['vmid'])
        return nfvcl_vmid[0]

    def __get_storage_path(self, storage_id: str):
        stdout = self.__execute_ssh_command('pvesh get /storage --output-format json')
        storages = json.loads(stdout.readline())
        for item in storages:
            if item['storage'] == storage_id and 'iso' in item['content']:
                return item['path']
        return None

    def __create_ci_qcow_folders(self):
        self.__execute_ssh_command(f'mkdir -p {self.path}/snippets')
        self.__execute_ssh_command(f'mkdir -p {self.path}/template/qcow')
        self.__execute_ssh_command(f'mkdir -p /root/scripts')

    def __load_scripts(self) -> None:
        ftp_client = self.ssh.open_sftp()
        ftp_client.put(f"{rel_path('scripts/image_script.sh')}", "/root/scripts/image_script.sh")
        self.__execute_ssh_command("chmod +x /root/scripts/image_script.sh")
        ftp_client.close()

    def __load_cloud_init(self, cloud_init: str, cloud_init_path: str) -> None:
        self.__execute_ssh_command(f"echo -e '{cloud_init}' > {cloud_init_path}")

    def __download_cloud_image(self, image_url, image_name):
        self.__execute_ssh_command(f'/root/scripts/image_script.sh {image_url} {self.path}/template/qcow/{image_name}.qcow2')

    def __get_macs(self, vmid: int):
        stdout = self.__execute_ssh_command(f"qm config {vmid} | grep -E 'net[0-9]+'")
        net_devices = stdout.readlines()
        macs = list()
        for net_device in net_devices:
            macs.append(net_device.split("virtio=")[1].split(",")[0].strip().lower())
        return macs

    def __parse_proxmox_addresses(self, vm_resource: VmResource, vmid):
        stdout = self.__execute_ssh_command(f'qm agent {vmid} network-get-interfaces')
        net_informations = json.loads(' '.join(stdout.readlines()))
        macs_of_interest = self.__get_macs(vmid)
        for interface in net_informations:
            mac = interface["hardware-address"]
            if mac in macs_of_interest:
                interface_name = interface['name']
                ip = None
                cidr = None
                if "ip-addresses" in interface.keys():
                    ip = interface["ip-addresses"][0]["ip-address"]
                    prefix = interface["ip-addresses"][0]["prefix"]
                    cidr = f"{ip}/{prefix}"
                fixed = VmResourceNetworkInterfaceAddress(interface_name=interface_name, ip=ip, mac=mac, cidr=cidr)
                vm_resource.network_interfaces[vm_resource.management_network] = VmResourceNetworkInterface(fixed=fixed)

    def __get_disks_memory(self, vmid: int):
        '''
        Retrieves disk memory space
        Args:
            vmid: id of virtual machine

        Returns: Positional array of disk memory

        '''
        stdout = self.__execute_ssh_command(f"qm config {vmid} | grep -E 'scsi[0-9]+:'")
        disk_devices = stdout.readlines()
        if disk_devices is not None:
            disks_memory = list()
            for disk in disk_devices:
                disks_memory.append(int(disk.split("size=")[1].split("M")[0].strip()))
            return disks_memory
        else:
            raise VirtualizationProviderProxmoxException(f"Non disk devices found for VM-ID: {vmid}")

    def resize_disk(self, vmid: int, desidered_size: int):
        size = self.__get_disks_memory(vmid)[0]
        desidered_size = desidered_size * 1024
        if desidered_size > size:
            size_to_add = math.ceil((desidered_size - size) / 1024)
            self.__execute_ssh_command(f'qm resize {vmid} scsi0 +{size_to_add}G')
        else:
            raise VirtualizationProviderProxmoxException(f"Disk of VM: {vmid}, is already larger than the desired size")

    def qemu_guest_agent_ready(self, vmid: int) -> bool:
        exit_status = 1
        while exit_status != 0:
            stdin, stdout, stderr = self.ssh.exec_command(f"qm agent {vmid} ping")
            exit_status = stdout.channel.recv_exit_status()
        return True

    def __execute_ssh_command(self, command: str):
        stdin, stdout, stderr = self.ssh.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            raise VirtualizationProviderProxmoxException(f"Error executing command: {command}")
        else:
            return stdout

    def __configure_vm_ansible(self, vm_resource_configuration: VmResourceAnsibleConfiguration) -> dict:
        nfvcl_tmp_dir = Path("/tmp/nfvcl/playbook")
        nfvcl_tmp_dir.mkdir(exist_ok=True, parents=True)

        playbook_str = vm_resource_configuration.dump_playbook()

        with open(Path(nfvcl_tmp_dir, f"{self.blueprint.id}_{vm_resource_configuration.vm_resource.name}.yml"), "w+") as f:
            f.write(playbook_str)

        # Wait for SSH to be ready, this is needed because sometimes cloudinit is still not finished and the server doesn't allow password connections
        self.__wait_for_ssh_to_be_ready(
            vm_resource_configuration.vm_resource.access_ip,
            22,
            vm_resource_configuration.vm_resource.username,
            vm_resource_configuration.vm_resource.password,
            300,
            5
        )

        ansible_runner_result, fact_cache = run_ansible_playbook(
            vm_resource_configuration.vm_resource.access_ip,
            vm_resource_configuration.vm_resource.username,
            vm_resource_configuration.vm_resource.password,
            playbook_str,
            self.logger
        )

        if ansible_runner_result.status == "failed":
            raise VirtualizationProviderProxmoxException("Error running ansible configurator")

        return fact_cache

    def __wait_for_ssh_to_be_ready(self, host: str, port: int, user: str, passwd: str, timeout: int, retry_interval: float) -> bool:
        self.logger.debug(f"Starting SSH connection to {host}:{port} as user <{user}> and passwd <{passwd}>. Timeout is {timeout}, retry interval is {retry_interval}")
        client = paramiko.client.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        timeout_start = time.time()
        while time.time() < timeout_start + timeout:
            try:
                client.connect(host, port, username=user, password=passwd, allow_agent=False, look_for_keys=False)
                self.logger.debug('SSH transport is available!')
                client.close()
                return True
            except paramiko.ssh_exception.SSHException as e:
                # socket is open, but not SSH service responded
                self.logger.debug(f"Socket is open, but not SSH service responded: {e}")
                time.sleep(retry_interval)
                continue

            except paramiko.ssh_exception.NoValidConnectionsError as e:
                self.logger.debug('SSH transport is not ready...')
                time.sleep(retry_interval)
                continue
        return False
