import ipaddress
import json
import math
import re
from enum import Enum
from pathlib import Path
from typing import Dict, List

import httpx
import paramiko
from httpx import Response

from blueprints_ng.cloudinit_builder import CloudInit, CloudInitNetworkRoot
from blueprints_ng.providers.configurators.ansible_utils import run_ansible_playbook
from blueprints_ng.providers.virtualization.common.models.netplan import VmAddNicNetplanConfigurator
from blueprints_ng.providers.virtualization.common.utils import wait_for_ssh_to_be_ready
from blueprints_ng.providers.virtualization.proxmox.models.models import ProxmoxZones, ProxmoxZone, Subnets, Subnet, \
    ProxmoxNetsDevice, ProxmoxNodes, ProxmoxMac
from blueprints_ng.providers.virtualization.virtualization_provider_interface import VirtualizationProviderException, \
    VirtualizationProviderInterface, VirtualizationProviderData
from blueprints_ng.resources import VmResource, VmResourceConfiguration, VmResourceNetworkInterfaceAddress, \
    VmResourceNetworkInterface, VmResourceAnsibleConfiguration, NetResource
from blueprints_ng.utils import rel_path

cloud_init_packages = ['qemu-guest-agent']
cloud_init_runcmd = ["systemctl enable qemu-guest-agent.service", "systemctl start qemu-guest-agent.service"]


class ApiRequestType(Enum):
    POST = "POST"
    PUT = "PUT"
    GET = "GET"
    DELETE = "DELETE"


class VirtualizationProviderDataProxmox(VirtualizationProviderData):
    proxmox_dict: Dict[str, str] = {}
    proxmox_macs: Dict[str, List[ProxmoxMac]] = {}
    proxmox_net_device: ProxmoxNetsDevice = ProxmoxNetsDevice()
    proxmox_vnet: List[str] = []
    proxmox_node_name: str = ""


class VirtualizationProviderProxmoxException(VirtualizationProviderException):
    pass


class VirtualizationProviderProxmox(VirtualizationProviderInterface):

    def __init__(self, area, blueprint):
        super().__init__(area, blueprint)

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
        if len(self.data.proxmox_node_name) == 0:
            response = self.__execute_rest_request("nodes", {}, ApiRequestType.GET)
            nodes: ProxmoxNodes = ProxmoxNodes.model_validate(response.json())
            self.data.proxmox_node_name = nodes.data[0].node

        self.logger.info(f"Creating VM {vm_resource.name}")
        self.__download_cloud_image(f'{vm_resource.image.url}', f'{vm_resource.image.name}')
        user_cloud_init = CloudInit(password=vm_resource.password,
                                    packages=cloud_init_packages,
                                    ssh_authorized_keys=self.vim.ssh_keys,
                                    runcmd=cloud_init_runcmd).build_cloud_config()

        netwotk_cloud_init: CloudInitNetworkRoot = CloudInitNetworkRoot()
        vmid = self.__get_free_vmid()

        user_cloud_init_path = f"{self.path}/snippets/user_cloud_init_{vmid}_{self.blueprint.id}.yaml"
        network_cloud_init_path = f"{self.path}/snippets/network_cloud_init_{vmid}_{self.blueprint.id}.yaml"

        self.__load_cloud_init(cloud_init=user_cloud_init, cloud_init_path=user_cloud_init_path)

        interface0 = self.data.proxmox_net_device.add_net_device(str(vmid))
        self.__execute_ssh_command(f'qm create {vmid} --agent 1 --memory {vm_resource.flavor.memory_mb} --name {vm_resource.get_name_k8s_format()} --cores {vm_resource.flavor.vcpu_count} --sockets 1 --cpu {vm_resource.flavor.vcpu_type} --{interface0} virtio,bridge={vm_resource.management_network},firewall=0 --scsihw virtio-scsi-pci')

        for net in vm_resource.additional_networks:
            interface = self.data.proxmox_net_device.add_net_device(str(vmid))
            self.__execute_ssh_command(f'qm set {vmid} --{interface} virtio,bridge={net},firewall=0')

        self.__get_macs(vmid)

        for mac in self.data.proxmox_macs[str(vmid)]:
            if mac.net_name == vm_resource.management_network:
                netwotk_cloud_init.add_device(mac.interface_name, mac.mac)
            else:
                netwotk_cloud_init.add_device(mac.interface_name, mac.mac, override=True)

        self.__load_cloud_init(cloud_init=netwotk_cloud_init.build_cloud_config(), cloud_init_path=network_cloud_init_path)

        self.data.proxmox_dict[vm_resource.id] = str(vmid)
        self.blueprint.to_db()
        self.__execute_ssh_command(f'qm importdisk {vmid} {self.path}/template/qcow/{vm_resource.image.name}.qcow2 {self.vim.vim_proxmox_storage_volume}')
        self.__execute_ssh_command(f'qm set {vmid} --scsi0 {self.vim.vim_proxmox_storage_volume}:vm-{vmid}-disk-0,discard=on,iothread=on,cache=writethrough')
        self.resize_disk(vmid, int(vm_resource.flavor.storage_gb))
        self.__execute_ssh_command(f'qm set {vmid} --ide2 {self.vim.vim_proxmox_storage_volume}:cloudinit')
        self.__execute_ssh_command(f"qm set {vmid} --boot order=scsi0")
        self.__execute_ssh_command(f'qm set {vmid} --cicustom "user=local:snippets/user_cloud_init_{vmid}_{self.blueprint.id}.yaml,network=local:snippets/network_cloud_init_{vmid}_{self.blueprint.id}.yaml"')

        self.blueprint.to_db()

        # Getting detailed info about the networks attached to the machine
        self.__execute_ssh_command(f"qm start {vmid}")

        # Loop until qemu-agent is ready
        self.qemu_guest_agent_ready(vmid)
        self.__parse_proxmox_addresses(vm_resource, vmid)

        # Find the IP to use for configuring the VMte
        if vm_resource.management_network in vm_resource.network_interfaces.keys() and len(vm_resource.network_interfaces[vm_resource.management_network]) > 0:
            vm_resource.access_ip = vm_resource.network_interfaces[vm_resource.management_network][0].fixed.ip
        else:
            raise VirtualizationProviderProxmoxException(f"Error {vm_resource.name} has no an IP assigned")

        # The VM is now created
        vm_resource.created = True

        self.logger.success(f"Creating VM {vm_resource.name} finished")
        self.blueprint.to_db()

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        # The parent method checks if the resource is created and throw an exception if not
        super().configure_vm(vm_resource_configuration)
        self.logger.info(f"Configuring VM {vm_resource_configuration.vm_resource.name}")

        configurator_facts = None

        # Different handlers for different configuration types
        if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):  # VmResourceNativeConfiguration
            configurator_facts = self.__configure_vm_ansible(vm_resource_configuration)

        self.logger.success(f"Configuring VM {vm_resource_configuration.vm_resource.name} finished")
        self.blueprint.to_db()

        return configurator_facts

    def destroy_vm(self, vm_resource: VmResource):
        vmid = self.data.proxmox_dict[vm_resource.id]
        self.__execute_ssh_command(f"qm stop {vmid}")
        self.__execute_ssh_command(f"qm destroy {vmid} --purge 1 --destroy-unreferenced-disks 1")
        self.__execute_ssh_command(f"rm {self.path}/snippets/user_cloud_init_{vmid}_{self.blueprint.id}.yaml")
        self.__execute_ssh_command(f"rm {self.path}/snippets/network_cloud_init_{vmid}_{self.blueprint.id}.yaml")
        del self.data.proxmox_dict[vm_resource.id]

    def final_cleanup(self):
        for vnet in self.data.proxmox_vnet:
            self.__delete_sdn_vnet(vnet)

    def create_net(self, net_resource: NetResource):
        self.__create_sdn_vnet(net_resource)
        self.__create_sdn_subnet(net_resource)

    def attach_net(self, vm_resource: VmResource, net_name: str):
        vm_resource.additional_networks.append(net_name)
        vmid = self.data.proxmox_dict[vm_resource.id]
        interface = self.data.proxmox_net_device.add_net_device(str(vmid))
        self.__execute_ssh_command(f'qm set {vmid} --{interface} virtio,bridge={net_name},firewall=0')
        self.__get_macs(int(vmid))

        for mac in self.data.proxmox_macs[vmid]:
            if mac.hw_interface_name == interface:
                self.__configure_vm_ansible(VmAddNicNetplanConfigurator(vm_resource=vm_resource, nic_name=mac.interface_name, mac_address=mac.mac))

        self.__parse_proxmox_addresses(vm_resource, vmid)

        self.logger.success(f"Network {net_name} attached to VM {vm_resource.name}")
        self.blueprint.to_db()

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
        pattern = re.compile("^net[0-9]+$")
        response = self.__execute_rest_request(f"nodes/{self.data.proxmox_node_name}/qemu/{vmid}/config", {}, r_type=ApiRequestType.GET)
        config = response.json()["data"]
        for key in config.keys():
            if re.match(pattern, key):
                tmp = config[key].split(",")
                mac = ProxmoxMac(
                    mac=tmp[0].split("virtio=")[1].strip().lower(),
                    net_name=tmp[1].split("bridge=")[1].strip(),
                    hw_interface_name=key,
                    interface_name=f"eth{key.split('net')[1]}"
                )
                if not str(vmid) in self.data.proxmox_macs.keys():
                    self.data.proxmox_macs[str(vmid)] = []
                if mac not in self.data.proxmox_macs[str(vmid)]:
                    self.data.proxmox_macs[str(vmid)].append(mac)

    def __parse_proxmox_addresses(self, vm_resource: VmResource, vmid):
        stdout = self.__execute_ssh_command(f'qm agent {vmid} network-get-interfaces')
        net_informations = json.loads(' '.join(stdout.readlines()))
        self.__get_macs(vmid)
        for interface in net_informations:
            mac = interface["hardware-address"]
            for p_mac in self.data.proxmox_macs[str(vmid)]:
                if mac == p_mac.mac:
                    interface_name = interface['name']
                    ip = None
                    cidr = None
                    if "ip-addresses" in interface.keys():
                        ip = interface["ip-addresses"][0]["ip-address"]
                        prefix = interface["ip-addresses"][0]["prefix"]
                        cidr = f"{ip}/{prefix}"
                    fixed = VmResourceNetworkInterfaceAddress(interface_name=interface_name, ip=ip, mac=mac, cidr=cidr)
                    if p_mac.net_name not in vm_resource.network_interfaces.keys():
                        vm_resource.network_interfaces[p_mac.net_name] = []
                    ni = VmResourceNetworkInterface(fixed=fixed)
                    if ni not in vm_resource.network_interfaces[p_mac.net_name]:
                        vm_resource.network_interfaces[p_mac.net_name].append(ni)

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
        self.logger.info("Waiting qemu guest agent")
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

    def __execute_rest_request(self, url: str, parameters: dict, r_type: ApiRequestType, my_data: dict = None, my_json=None):
        url_base = f"https://{self.vim.vim_url}:8006/api2/json/"
        with httpx.Client(base_url=url_base, verify=False) as client:
            header = {
                'Content-Type': 'application/json',
                'Authorization': 'PVEAPIToken=root@pam!APIToken=1dcaa25f-7d6a-44ce-aa63-6f73f10db3a6'
            }
            match r_type:
                case ApiRequestType.POST:
                    response = client.post(url, headers=header, params=parameters, data=my_data, json=my_json)
                case ApiRequestType.PUT:
                    response = client.put(url, headers=header, params=parameters, data=my_data)
                case ApiRequestType.GET:
                    response = client.get(url, headers=header, params=parameters)
                case ApiRequestType.DELETE:
                    response = client.delete(url, headers=header, params=parameters)
                case _:
                    raise VirtualizationProviderProxmoxException("Api request type not supported")

            self.logger.info(f"Status code: {response.status_code}")
            return response

    def __configure_vm_ansible(self, vm_resource_configuration: VmResourceAnsibleConfiguration) -> dict:
        nfvcl_tmp_dir = Path("/tmp/nfvcl/playbook")
        nfvcl_tmp_dir.mkdir(exist_ok=True, parents=True)

        playbook_str = vm_resource_configuration.dump_playbook()

        with open(Path(nfvcl_tmp_dir, f"{self.blueprint.id}_{vm_resource_configuration.vm_resource.name}.yml"), "w+") as f:
            f.write(playbook_str)

        # Wait for SSH to be ready, this is needed because sometimes cloudinit is still not finished and the server doesn't allow password connections
        wait_for_ssh_to_be_ready(
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

    def __get_nfvcl_sdn_zone(self) -> ProxmoxZone:
        response = self.__execute_rest_request("cluster/sdn/zones", {'type': 'simple'}, r_type=ApiRequestType.GET)
        zones: ProxmoxZones = ProxmoxZones.model_validate(response.json())
        for zone in zones.data:
            if zone.zone.lower() == "nfvcl":
                return zone
        raise VirtualizationProviderProxmoxException("NFVCL sdn zone not found, you must create a zone called nfvcl (case sensitive)")

    def __get_ips_for_subnets(self, cidr: str) -> (str, str, str):
        ips = ipaddress.ip_network(cidr)
        return ips[-2].__format__('s'), ips[2].__format__('s'), ips[-3].__format__('s')

    def __apply_sdn(self):
        self.logger.info("Applying sdn configuration")
        stdout = self.__execute_ssh_command(f'pvesh set /cluster/sdn')

    # def __create_sdn_zone(self, zone: NetResource):
    #     stdout = self.__execute_ssh_command(f'pvesh create /cluster/sdn/zones --type simple --zone {zone.name}')
    #     self.__create_sdn_vnet("Vprova", zone)
    #     print("Ciao")
    #     stdout = self.__execute_ssh_command(f'pvesh delete /cluster/sdn/zones/{zone.name}')
    #     pass
    def __create_sdn_vnet(self, vnet: NetResource):
        self.logger.info(f"Creating Vnet {vnet.name}")
        nfvcl_zone = self.__get_nfvcl_sdn_zone()
        stdout : Response = self.__execute_rest_request(f'cluster/sdn/vnets', {}, r_type=ApiRequestType.POST, my_json={'vnet': f'{vnet.name}', 'zone': f'{nfvcl_zone.zone}'})
        if stdout.reason_phrase != "OK":
            raise VirtualizationProviderProxmoxException(f"{stdout.reason_phrase}")
        self.__apply_sdn()
        self.data.proxmox_vnet.append(vnet.name.lower())

    # def __get_sdn_vnet(self, vnet_name: str):
    #     response = self.__execute_rest_request(f'cluster/sdn/vnets/{vnet_name}', {}, ApiRequestType.GET)
    #     data = response.json()
    #     if data['data'] is not None:
    #         raise VirtualizationProviderProxmoxException(f"Vnet {vnet_name} already exists")

    def __delete_sdn_vnet(self, vnet: str):
        self.logger.info(f"Deleting Vnet: {vnet}")
        response = self.__execute_rest_request(f"cluster/sdn/vnets/{vnet}/subnets", parameters={}, r_type=ApiRequestType.GET)
        subnets: Subnets = Subnets.model_validate(response.json())
        for subnet in subnets.data:
            self.logger.info(f"Deleting {vnet} subnets: {subnet.id}")
            self.__delete_sdn_subnet(subnet)
        self.__execute_ssh_command(f"pvesh delete /cluster/sdn/vnets/{vnet}")
        self.__apply_sdn()
        self.data.proxmox_vnet.remove(vnet.lower())

    def __create_sdn_subnet(self, vnet: NetResource):
        self.logger.info(f"Creating Vnet Subnet {vnet.cidr}")
        gateway, start_dhcp, end_dhcp = self.__get_ips_for_subnets(vnet.cidr)
        stdout = self.__execute_rest_request(f"cluster/sdn/vnets/{vnet.name}/subnets", {}, r_type=ApiRequestType.POST, my_json={'subnet': f'{vnet.cidr}', 'type': 'subnet', 'gateway' : f'{gateway}', 'dhcp-range' : f'start-address={start_dhcp},end-address={end_dhcp}'})
        if stdout.reason_phrase != "OK":
            raise VirtualizationProviderProxmoxException(f"{stdout.reason_phrase}")
        self.__apply_sdn()

    # def __get_sdn_subnet(self, vnet: NetResource):
    #     subnet_id = f"nfvcl-{vnet.cidr.replace('/', '-')}"
    #     response = self.__execute_rest_request(f'cluster/sdn/vnets/{vnet.name}/subnets/{subnet_id}', {}, ApiRequestType.GET)
    #     data = response.json()
    #     if data['data'] is not None:
    #         raise VirtualizationProviderProxmoxException(f"Subent {subnet_id} in Vnet {vnet.name} already exists")

    def __delete_sdn_subnet(self, subnet: Subnet):
        stdout = self.__execute_ssh_command(f'pvesh delete /cluster/sdn/vnets/{subnet.vnet}/subnets/{subnet.id}')
        self.__apply_sdn()
