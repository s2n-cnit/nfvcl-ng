import ipaddress
import math
import re
from enum import Enum
from time import sleep
from typing import Dict, List

from pydantic import Field, TypeAdapter

from nfvcl_core.blueprints.cloudinit_builder import CloudInit, CloudInitNetworkRoot
from nfvcl_core.managers.vim_clients_manager import ProxmoxVimClient
from nfvcl_core.providers.virtualization.common.models.netplan import VmAddNicNetplanConfigurator, \
    NetplanInterface
from nfvcl_core.providers.virtualization.common.utils import configure_vm_ansible
from nfvcl_core.providers.virtualization.proxmox.models.models import ProxmoxZone, Subnet, \
    ProxmoxNetsDevice, ProxmoxMac, ProxmoxTicket, ProxmoxNode, Vnet
from nfvcl_core.providers.virtualization.virtualization_provider_interface import \
    VirtualizationProviderException, \
    VirtualizationProviderInterface, VirtualizationProviderData
from nfvcl_core.utils.blue_utils import rel_path
from nfvcl_core_models.resources import VmResource, VmResourceConfiguration, VmResourceNetworkInterfaceAddress, \
    VmResourceNetworkInterface, VmResourceAnsibleConfiguration, NetResource
from nfvcl_core_models.vim.vim_models import VimModel

cloud_init_packages = ['qemu-guest-agent']
cloud_init_runcmd = ["systemctl enable qemu-guest-agent.service", "systemctl start qemu-guest-agent.service"]


class ApiRequestType(Enum):
    POST = "POST"
    PUT = "PUT"
    GET = "GET"
    DELETE = "DELETE"


class VirtualizationProviderDataProxmox(VirtualizationProviderData):
    proxmox_dict: Dict[str, str] = Field(default_factory=dict)
    proxmox_macs: Dict[str, List[ProxmoxMac]] = Field(default_factory=dict)
    proxmox_net_device: ProxmoxNetsDevice = ProxmoxNetsDevice()
    proxmox_vnet: Dict[str, str] = Field(default_factory=dict)
    proxmox_node_name: str = ""
    proxmox_credentials: ProxmoxTicket = ProxmoxTicket()


class VirtualizationProviderProxmoxException(VirtualizationProviderException):
    pass


class VirtualizationProviderProxmox(VirtualizationProviderInterface):
    proxmox_vim_client: ProxmoxVimClient
    data: VirtualizationProviderDataProxmox
    vim: VimModel

    def init(self):
        self.data: VirtualizationProviderDataProxmox = VirtualizationProviderDataProxmox()
        self.vim = self.topology.get_vim_by_area(self.area)
        self.proxmox_vim_client = self.vim_clients_manager.get_proxmox_client(self, self.vim.name)
        self.path = self.__get_storage_path(self.vim.vim_proxmox_storage_id)
        self.__create_ci_qcow_folders()
        self.__load_scripts()
        if len(self.data.proxmox_node_name) == 0:
            if self.vim.vim_proxmox_node:
                self.data.proxmox_node_name = self.vim.vim_proxmox_node
            else:
                self.data.proxmox_node_name = self.get_node_by_ip()

    def get_vim_info(self):
        return self.vim

    def get_node_by_ip(self):
        response = self.__execute_proxmox_request(
            url="nodes",
            r_type=ApiRequestType.GET
        )
        ta = TypeAdapter(List[ProxmoxNode])
        nodes = ta.validate_python(response)
        for node in nodes:
            node_details = self.proxmox_vim_client.proxmoxer.nodes(node.node).network.get()
            for interface in node_details:
                if "address" in interface and interface["address"] == self.vim.vim_url:
                    return node.node
        raise VirtualizationProviderProxmoxException(f"Node with ip {self.vim.vim_url} not found")

    def __pre_creation_check(self, networks: List[str]):
        response = self.__execute_proxmox_request(
            url=f"cluster/sdn/vnets",
            r_type=ApiRequestType.GET
        )
        ta = TypeAdapter(List[Vnet])
        vnets = ta.validate_python(response)

        # Check if subnet has gateway set, no gateway = DHCP doesn't work in proxmox
        for vnet in vnets:
            if vnet.vnet in networks:
                response = self.__execute_proxmox_request(
                    url=f"cluster/sdn/vnets/{vnet.vnet}/subnets",
                    r_type=ApiRequestType.GET
                )
                ta = TypeAdapter(List[Subnet])
                subnets = ta.validate_python(response)
                if len(subnets) == 1:
                    if subnets[0].gateway is None:
                        raise VirtualizationProviderProxmoxException(f"Error Subnet of Vnet {vnet.vnet} has no gateway defined")
                else:
                    raise VirtualizationProviderProxmoxException(f"Error Vnet {vnet.vnet} has no subnets or more than 1 subnet")

    def create_vm(self, vm_resource: VmResource):
        tmp_networks = vm_resource.additional_networks.copy()
        tmp_networks.append(vm_resource.management_network)
        self.__pre_creation_check(tmp_networks)
        self.logger.info(f"Creating VM {vm_resource.name} on node {self.data.proxmox_node_name}")
        self.__download_cloud_image(f'{vm_resource.image.url}', f'{vm_resource.image.name}')
        c_init = CloudInit(hostname=vm_resource.name,
                           packages=cloud_init_packages,
                           ssh_authorized_keys=self.vim.ssh_keys,
                           runcmd=cloud_init_runcmd)
        c_init.add_user(vm_resource.username, vm_resource.password)
        user_cloud_init = c_init.build_cloud_config()

        netwotk_cloud_init: CloudInitNetworkRoot = CloudInitNetworkRoot()
        vmid = self.__get_free_vmid()

        user_cloud_init_path = f"{self.path}/snippets/user_cloud_init_{vmid}_{self.blueprint_id}.yaml"
        network_cloud_init_path = f"{self.path}/snippets/network_cloud_init_{vmid}_{self.blueprint_id}.yaml"

        self.__load_cloud_init(cloud_init=user_cloud_init, cloud_init_path=user_cloud_init_path)

        interface0 = self.data.proxmox_net_device.add_net_device(str(vmid))
        vm_to_create = {
            "vmid": vmid,
            "name": vm_resource.get_name_k8s_format(),
            "memory": vm_resource.flavor.memory_mb,
            "cores": vm_resource.flavor.vcpu_count,
            "sockets": 1,
            "cpu": vm_resource.flavor.vcpu_type,
            "scsihw": "virtio-scsi-pci",
            "tags": "nfvcl", # If you want add more tags, you have to separate them with ";"
            "agent": 1,
            "scsi0": f"file={self.vim.vim_proxmox_storage_volume}:0,import-from=local:0/{vm_resource.image.name}.qcow2,iothread=on",
            "ide2": f"{self.vim.vim_proxmox_storage_volume}:cloudinit",
            "boot": "order=scsi0",
            "cicustom": f"user=local:snippets/user_cloud_init_{vmid}_{self.blueprint_id}.yaml,network=local:snippets/network_cloud_init_{vmid}_{self.blueprint_id}.yaml"
        }

        vm_to_create[interface0] = f"virtio,bridge={self.data.proxmox_vnet[vm_resource.management_network]},firewall=0" if vm_resource.management_network in self.data.proxmox_vnet.keys() else f"virtio,bridge={vm_resource.management_network},firewall=0"

        for net in vm_resource.additional_networks:
            interface = self.data.proxmox_net_device.add_net_device(str(vmid))
            vm_to_create[interface] = f"virtio,bridge={self.data.proxmox_vnet[net]},firewall=0" if net in self.data.proxmox_vnet.keys() else f"virtio,bridge={net},firewall=0"

        self.__execute_proxmox_request(
            url=f"nodes/{self.data.proxmox_node_name}/qemu",
            parameters=vm_to_create,
            r_type=ApiRequestType.POST,
            node_name=self.data.proxmox_node_name
        )
        self.resize_disk(vmid, int(vm_resource.flavor.storage_gb), "scsi0")

        self.__get_macs(vmid)

        for mac in self.data.proxmox_macs[str(vmid)]:
            if mac.net_name == vm_resource.management_network:
                netwotk_cloud_init.add_device(mac.interface_name, mac.mac)
            else:
                netwotk_cloud_init.add_device(mac.interface_name, mac.mac, override=True)

        self.__load_cloud_init(cloud_init=netwotk_cloud_init.build_cloud_config(), cloud_init_path=network_cloud_init_path)

        self.data.proxmox_dict[vm_resource.id] = str(vmid)
        self.save_to_db()

        self.__execute_proxmox_request(
            url=f"nodes/{self.data.proxmox_node_name}/qemu/{vmid}/status/start",
            node_name=self.data.proxmox_node_name,
            r_type=ApiRequestType.POST
        )

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
        self.save_to_db()

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        # The parent method checks if the resource is created and throw an exception if not
        super().configure_vm(vm_resource_configuration)
        self.logger.info(f"Configuring VM {vm_resource_configuration.vm_resource.name}")

        configurator_facts = None

        # Different handlers for different configuration types
        if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):  # VmResourceNativeConfiguration
            configurator_facts = configure_vm_ansible(vm_resource_configuration, self.blueprint_id, logger_override=self.logger)

        self.logger.success(f"Configuring VM {vm_resource_configuration.vm_resource.name} finished")
        self.save_to_db()

        return configurator_facts

    def destroy_vm(self, vm_resource: VmResource):
        self.logger.info(f"Destroying VM {vm_resource.name}")
        if vm_resource.id in self.data.proxmox_dict.keys():
            vmid = self.data.proxmox_dict[vm_resource.id]
            self.logger.debug(f"Stopping VM {vmid}")
            self.__execute_proxmox_request(
                url=f"nodes/{self.data.proxmox_node_name}/qemu/{vmid}/status/stop",
                node_name=self.data.proxmox_node_name,
                r_type=ApiRequestType.POST
            )
            self.logger.debug(f"Destroying VM {vmid}")
            self.__execute_proxmox_request(
                url=f"nodes/{self.data.proxmox_node_name}/qemu/{vmid}",
                parameters={"purge": 1},
                node_name=self.data.proxmox_node_name,
                r_type=ApiRequestType.DELETE
            )
            self.__execute_ssh_command(f"rm {self.path}/snippets/user_cloud_init_{vmid}_{self.blueprint_id}.yaml")
            self.__execute_ssh_command(f"rm {self.path}/snippets/network_cloud_init_{vmid}_{self.blueprint_id}.yaml")
            del self.data.proxmox_dict[vm_resource.id]
            self.logger.success(f"VM {vmid} destroyed")

    def final_cleanup(self):
        for vnet in list(self.data.proxmox_vnet.keys()).copy():
            self.__delete_sdn_vnet(vnet)
        self.vim_clients_manager.release_client(self, self.vim.name)

    def create_net(self, net_resource: NetResource):
        self.__create_sdn_vnet(net_resource)
        self.__create_sdn_subnet(net_resource)

    def attach_nets(self, vm_resource: VmResource, nets_name: List[str]) -> List[str]:
        netplan_interfaces: List[NetplanInterface] = []
        interfaces = []
        vmid = self.data.proxmox_dict[vm_resource.id]

        for net in nets_name:
            vm_resource.additional_networks.append(net)
            interface = self.data.proxmox_net_device.add_net_device(str(vmid))
            interfaces.append(interface)
            self.__execute_proxmox_request(
                url=f'nodes/{self.data.proxmox_node_name}/qemu/{vmid}/config',
                parameters={f"{interface}": f"virtio,bridge={self.data.proxmox_vnet[net]},firewall=0"},
                r_type=ApiRequestType.PUT)

        self.__get_macs(int(vmid))

        for interface in interfaces:
            for mac in self.data.proxmox_macs[vmid]:
                if mac.hw_interface_name == interface:
                    tmp = NetplanInterface(
                        nic_name=mac.interface_name,
                        mac_address=mac.mac
                    )
                    netplan_interfaces.append(tmp)

        configure_vm_ansible(VmAddNicNetplanConfigurator(vm_resource=vm_resource, nics=netplan_interfaces), self.blueprint_id, logger_override=self.logger)

        self.__parse_proxmox_addresses(vm_resource, vmid)

        self.logger.success(f"Network {', '.join(nets_name)} attached to VM {vm_resource.name}")
        self.save_to_db()

        ips = []
        for net in nets_name:
            for interface in netplan_interfaces:
                for net_interface in vm_resource.network_interfaces[net]:
                    if net_interface.fixed.interface_name == interface.nic_name and net_interface.fixed.ip not in ips:
                        ips.append(net_interface.fixed.ip)

        return ips

    def __get_free_vmid(self) -> int:
        nfvcl_vmid = list(range(10000, 11000))
        vms = self.__execute_proxmox_request(
            url="cluster/resources",
            parameters={"type": "vm"},
            r_type=ApiRequestType.GET
        )
        for item in vms:
            if item['vmid'] in nfvcl_vmid:
                nfvcl_vmid.remove(item['vmid'])
        return nfvcl_vmid[0]

    def __get_storage_path(self, storage_id: str):
        storages = self.__execute_proxmox_request(
            url="storage",
            r_type=ApiRequestType.GET
        )
        for item in storages:
            if item['storage'] == storage_id and 'iso' in item['content']:
                return item['path']
        return None

    def __create_ci_qcow_folders(self):
        self.__execute_ssh_command(f'mkdir -p {self.path}/snippets')
        self.__execute_ssh_command(f'mkdir -p {self.path}/images/0')
        self.__execute_ssh_command(f'mkdir -p /root/scripts')

    def __load_scripts(self) -> None:
        ftp_client = self.proxmox_vim_client.ssh_client.open_sftp()
        ftp_client.put(f"{rel_path('scripts/image_script.sh')}", "/root/scripts/image_script.sh")
        self.__execute_ssh_command("chmod +x /root/scripts/image_script.sh")
        ftp_client.close()

    def __load_cloud_init(self, cloud_init: str, cloud_init_path: str) -> None:
        self.__execute_ssh_command(f"echo -e '{cloud_init}' > {cloud_init_path}")

    def __download_cloud_image(self, image_url, image_name):
        # TODO when supported
        # response = httpx.get(f"{image_url}.SHA256SUM")
        # checksum = response.content.split()[0]
        # download_args = {"url": image_url, "content": "import", "filename": f"{image_name}.img", "checksum": checksum, "checksum-algorithm": "sha256"}
        # self.proxmox_vim_client.proxmoxer.nodes(self.data.proxmox_node_name).storage(self.vim.vim_proxmox_storage_id)("download-url").post(**download_args)
        self.__execute_ssh_command(f'/root/scripts/image_script.sh {image_url} {self.path}/images/0/{image_name}.qcow2')

    def __get_macs(self, vmid: int):
        config = self.__execute_proxmox_request(
            url=f"nodes/{self.data.proxmox_node_name}/qemu/{vmid}/config",
            r_type=ApiRequestType.GET
        )
        for key in config.keys():
            if re.match("^net[0-9]+$", key):
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
        net_informations = self.__execute_proxmox_request(
            url=f"nodes/{self.data.proxmox_node_name}/qemu/{vmid}/agent/network-get-interfaces",
            r_type=ApiRequestType.GET
        )
        self.__get_macs(vmid)
        for interface in net_informations["result"]:
            mac = interface["hardware-address"]
            for p_mac in self.data.proxmox_macs[str(vmid)]:
                if mac == p_mac.mac:
                    interface_name = interface['name']
                    ip = None
                    cidr = None
                    if "ip-addresses" in interface.keys():
                        ip = interface["ip-addresses"][0]["ip-address"]
                        prefix = interface["ip-addresses"][0]["prefix"]
                        base_network = ipaddress.IPv4Network(f'{ip}/{prefix}', strict=False).network_address
                        cidr = f'{base_network}/{prefix}'
                    fixed = VmResourceNetworkInterfaceAddress(interface_name=interface_name, ip=ip, mac=mac, cidr=cidr)
                    key = next((key for key, value in self.data.proxmox_vnet.items() if value == p_mac.net_name), None)

                    if key and key not in vm_resource.network_interfaces.keys():
                        vm_resource.network_interfaces[key] = []
                    elif p_mac.net_name not in vm_resource.network_interfaces.keys():
                        vm_resource.network_interfaces[p_mac.net_name] = []

                    ni = VmResourceNetworkInterface(fixed=fixed)
                    if key and ni not in vm_resource.network_interfaces[key]:
                        vm_resource.network_interfaces[key].append(ni)
                    elif ni not in vm_resource.network_interfaces[p_mac.net_name]:
                        vm_resource.network_interfaces[p_mac.net_name].append(ni)
                    continue

    def __get_disks_memory(self, vmid: int):
        """
        Retrieves disk memory space
        Args:
            vmid: id of virtual machine

        Returns: Positional array of disk memory

        """
        config = self.__execute_proxmox_request(
            url=f"nodes/{self.data.proxmox_node_name}/qemu/{vmid}/config",
            r_type=ApiRequestType.GET
        )
        disks = list(filter(lambda x: re.match('scsi[0-9]+', x), config.keys()))
        if disks is not None:
            disks_memory = list()
            for disk in disks:
                size: str = config[disk].split("size=")[1]  # 10G or 10M
                if size:
                    disks_memory.append((size, disk))
                else:
                    raise VirtualizationProviderProxmoxException(f"Disk size unit not supported: {size}")
            return disks_memory
        else:
            raise VirtualizationProviderProxmoxException(f"Non disk devices found for VM-ID: {vmid}")

    def resize_disk(self, vmid: int, desidered_size: int, disk: str):
        disks = self.__get_disks_memory(vmid)
        desidered_size = desidered_size * 1024
        for d in disks:
            if d[1] == disk:
                if "M" in d[0]:
                    size = int(d[0].split("M")[0])
                else:
                    size = int(d[0].split("G")[0]) * 1024
                if desidered_size > size:
                    size_to_add = math.ceil((desidered_size - size))
                    self.__execute_proxmox_request(
                        url=f"nodes/{self.data.proxmox_node_name}/qemu/{vmid}/resize",
                        parameters={
                            "disk": f"{d[1]}",
                            "size": f"+{size_to_add}M"
                        },
                        node_name=self.data.proxmox_node_name,
                        r_type=ApiRequestType.PUT
                    )
                else:
                    self.logger.warning(f"Disk of VM: {vmid}, is already larger than the desired size")

    def qemu_guest_agent_ready(self, vmid: int) -> bool:
        self.logger.info("Waiting qemu guest agent")
        exit_status = 1
        response = None
        while exit_status != 0:
            try:
                response = self.proxmox_vim_client.proxmoxer.nodes(self.data.proxmox_node_name).qemu(vmid).agent.ping.post()
                if response is not None:
                    exit_status = 0
            except Exception as e:
                self.logger.debug("Waiting...")
                sleep(3)
        return True

    def __execute_ssh_command(self, command: str):
        stdin, stdout, stderr = self.proxmox_vim_client.ssh_client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            raise VirtualizationProviderProxmoxException(f"Error executing command: {command}")
        else:
            return stdout

    def __execute_proxmox_request(self, url: str, r_type: ApiRequestType, node_name=None, parameters=None):
        match r_type:
            case ApiRequestType.GET:
                response = self.proxmox_vim_client.proxmoxer(url).get(**parameters if parameters else {})
            case ApiRequestType.POST:
                response = self.proxmox_vim_client.proxmoxer(url).post(**parameters if parameters else {})
            case ApiRequestType.PUT:
                response = self.proxmox_vim_client.proxmoxer(url).put(**parameters if parameters else {})
            case ApiRequestType.DELETE:
                response = self.proxmox_vim_client.proxmoxer(url).delete(**parameters if parameters else {})
            case _:
                raise VirtualizationProviderProxmoxException("Api request type not supported")

        if node_name:
            data = {"status": ""}
            while data["status"] != "stopped":
                output = f"{response.split(':')[5]}, VMid {response.split(':')[6]}" if response.split(':')[6] else f"{response.split(':')[5]}"
                self.logger.debug(f"Waiting for task: {output}")
                data = self.proxmox_vim_client.proxmoxer.nodes(node_name).tasks(response).status.get()
                sleep(3)

        return response

    def __get_nfvcl_sdn_zone(self) -> ProxmoxZone:
        response = self.__execute_proxmox_request(
            url="cluster/sdn/zones",
            r_type=ApiRequestType.GET
        )
        ta = TypeAdapter(List[ProxmoxZone])
        zones = ta.validate_python(response)
        for zone in zones:
            if zone.zone.lower() == "nfvcl":
                return zone
        raise VirtualizationProviderProxmoxException("NFVCL sdn zone not found, you must create a zone called nfvcl (case sensitive)")

    def __get_ips_for_subnets(self, cidr: str) -> (str, str, str):
        ips = ipaddress.ip_network(cidr)
        return ips[-2].__format__('s'), ips[2].__format__('s'), ips[-3].__format__('s')

    def __apply_sdn(self):
        self.logger.info("Applying sdn configuration")
        self.__execute_proxmox_request(
            url="cluster/sdn",
            node_name=self.data.proxmox_node_name,
            r_type=ApiRequestType.PUT
        )

    # def __create_sdn_zone(self, zone: NetResource):
    #     stdout = self.__execute_ssh_command(f'pvesh create /cluster/sdn/zones --type simple --zone {zone.name}')
    #     self.__create_sdn_vnet("Vprova", zone)
    #     print("Ciao")
    #     stdout = self.__execute_ssh_command(f'pvesh delete /cluster/sdn/zones/{zone.name}')
    #     pass
    def __create_sdn_vnet(self, vnet: NetResource):
        identifier = f'N{vnet.name.split("_")[1]}'
        self.logger.info(f"Creating Vnet {vnet.name}")
        nfvcl_zone = self.__get_nfvcl_sdn_zone()
        try:
            self.__execute_proxmox_request(
                url=f'cluster/sdn/vnets',
                r_type=ApiRequestType.POST,
                parameters={'vnet': f'{identifier}', 'zone': f'{nfvcl_zone.zone}', 'alias': f'{vnet.name}'}
            )
        except Exception as e:
            self.logger.error(f"Failed to create Vnet {vnet.name} for {e}")
            return
        self.__apply_sdn()
        self.data.proxmox_vnet[vnet.name] = identifier

    # def __get_sdn_vnet(self, vnet_name: str):
    #     response = self.__execute_rest_request(f'cluster/sdn/vnets/{vnet_name}', {}, ApiRequestType.GET)
    #     data = response.json()
    #     if data['data'] is not None:
    #         raise VirtualizationProviderProxmoxException(f"Vnet {vnet_name} already exists")

    def __delete_sdn_vnet(self, vnet: str):
        self.logger.info(f"Deleting Vnet: {vnet}")
        tmp = self.__execute_proxmox_request(
            url=f"cluster/sdn/vnets/{self.data.proxmox_vnet[vnet]}/subnets",
            r_type=ApiRequestType.GET
        )
        ta = TypeAdapter(List[Subnet])
        subnets = ta.validate_python(tmp)
        for subnet in subnets:
            self.logger.info(f"Deleting {vnet} subnets: {subnet.id}")
            self.__delete_sdn_subnet(subnet)
        self.__execute_proxmox_request(
            url=f"/cluster/sdn/vnets/{self.data.proxmox_vnet[vnet]}",
            r_type=ApiRequestType.DELETE
        )
        self.__apply_sdn()
        del self.data.proxmox_vnet[vnet]
        self.logger.success(f"Vnet {vnet} deleted")

    def __create_sdn_subnet(self, vnet: NetResource):
        self.logger.info(f"Creating Vnet Subnet {vnet.cidr}")
        gateway, start_dhcp, end_dhcp = self.__get_ips_for_subnets(vnet.cidr)
        try:
            self.__execute_proxmox_request(
                url=f"cluster/sdn/vnets/{self.data.proxmox_vnet[vnet.name]}/subnets",
                r_type=ApiRequestType.POST,
                parameters={
                    'subnet': f'{vnet.cidr}',
                    'type': 'subnet',
                    'gateway': f'{gateway}',
                    'dhcp-range': f'start-address={start_dhcp},end-address={end_dhcp}'
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to create Vnet Subnet {vnet.name} for {e}")
            return
        self.__apply_sdn()

    # def __get_sdn_subnet(self, vnet: NetResource):
    #     subnet_id = f"nfvcl-{vnet.cidr.replace('/', '-')}"
    #     response = self.__execute_rest_request(f'cluster/sdn/vnets/{vnet.name}/subnets/{subnet_id}', {}, ApiRequestType.GET)
    #     data = response.json()
    #     if data['data'] is not None:
    #         raise VirtualizationProviderProxmoxException(f"Subent {subnet_id} in Vnet {vnet.name} already exists")

    def __delete_sdn_subnet(self, subnet: Subnet):
        self.__execute_proxmox_request(
            url=f'/cluster/sdn/vnets/{subnet.vnet}/subnets/{subnet.id}',
            r_type=ApiRequestType.DELETE
        )
        self.__apply_sdn()
        self.logger.success(f"Subnet {subnet.id} deleted")
