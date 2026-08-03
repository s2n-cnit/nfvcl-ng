import ipaddress
import re
import uuid
from typing import Dict, List, Tuple, Set, Optional, cast

from pydantic import Field

from nfvcl_common.cloudinit_builder import CloudInit, CloudInitNetworkRoot
from nfvcl_common.utils.blue_utils import rel_path
from nfvcl_core_models.providers.providers import ProviderData
from nfvcl_core_models.resources import VmResource, VmResourceConfiguration, VmResourceNetworkInterfaceAddress, VmResourceNetworkInterface, VmResourceAnsibleConfiguration, NetResource, VmStatus, VmPowerStatus
from nfvcl_core_models.vim.vim_models import VimTypeEnum
from nfvcl_providers.vim_clients.proxmox_vim_client import ProxmoxVimClient, IMPORT_URL_VERSION, proxmox_sdn_vnet_identifier
from nfvcl_providers.virtualization.common.models.netplan import VmAddNicNetplanConfigurator, NetplanInterface
from nfvcl_providers.virtualization.common.utils import configure_vm_ansible, check_ssh_ready
from nfvcl_providers.virtualization.proxmox.models.models import ProxmoxNetsDevice, ProxmoxMac
from nfvcl_providers.virtualization.virtualization_provider_interface import VirtualizationProviderException, VirtualizationProviderInterface, VirtualizationProviderData

cloud_init_packages = ['qemu-guest-agent']
# cloud_init_runcmd = ["systemctl start qemu-guest-agent.service", "systemctl enable qemu-guest-agent.service"]
cloud_init_runcmd = ["systemctl start qemu-guest-agent.service"]


class ResourceGroupVirtualizationProviderDataProxmox(ProviderData):
    proxmox_dict: Dict[str, str] = Field(default_factory=dict)
    proxmox_macs: Dict[str, List[ProxmoxMac]] = Field(default_factory=dict)
    proxmox_net_device: ProxmoxNetsDevice = ProxmoxNetsDevice()
    proxmox_vnet: Dict[str, str] = Field(default_factory=dict)


class ProxmoxVimProviderData(ProviderData):
    resource_groups: Dict[str, ResourceGroupVirtualizationProviderDataProxmox] = Field(default_factory=dict)

    def get_resource_group_data(self, resource_group: str) -> ResourceGroupVirtualizationProviderDataProxmox:
        if resource_group not in self.resource_groups:
            self.resource_groups[resource_group] = ResourceGroupVirtualizationProviderDataProxmox()
        return self.resource_groups[resource_group]


class VirtualizationProviderDataProxmox(VirtualizationProviderData):
    vims: Dict[str, ProxmoxVimProviderData] = Field(default_factory=dict)

    def get_vim_data(self, vim_name: str) -> ProxmoxVimProviderData:
        if vim_name not in self.vims:
            self.vims[vim_name] = ProxmoxVimProviderData()
        return self.vims[vim_name]

class VirtualizationProviderProxmoxException(VirtualizationProviderException):
    pass


class VirtualizationProviderProxmox(VirtualizationProviderInterface):
    provider_vim_type = VimTypeEnum.PROXMOX
    data: VirtualizationProviderDataProxmox

    def init(self):
        self.data: VirtualizationProviderDataProxmox = VirtualizationProviderDataProxmox()

    def _get_client(self, area: int) -> ProxmoxVimClient:
        vim_client = cast(ProxmoxVimClient, self.get_vim_client(area))
        with open(rel_path('scripts/image_script.sh'), 'r') as script_file:
            vim_client.ensure_nfvcl_runtime_ready(script_file.read())
        return vim_client

    def _get_resource_group_data(self, client: ProxmoxVimClient, resource_group: str) -> ResourceGroupVirtualizationProviderDataProxmox:
        return self.data.get_vim_data(client.vim.name).get_resource_group_data(resource_group)

    def _delete_resource_group_data(self, client: ProxmoxVimClient, resource_group: str):
        return self.data.get_vim_data(client.vim.name).resource_groups.pop(resource_group, None)

    def create_vm(self, vm_resource: VmResource):
        client = self._get_client(vm_resource.area)
        rg_data = self._get_resource_group_data(client, vm_resource.resource_group)

        tmp_networks = vm_resource.additional_networks.copy()
        tmp_networks.append(vm_resource.management_network)
        client.pre_creation_check(tmp_networks)
        self.logger.info(f"Creating VM {vm_resource.name} on node {client.get_node_name()}")
        client.download_cloud_image(f"{vm_resource.image.url}", f"{vm_resource.image.name}")

        ssh_keys = []
        ssh_keys.extend(client.vim.ssh_keys or [])
        if vm_resource.flavor.ssh_keys:
            ssh_keys.extend(vm_resource.flavor.ssh_keys)

        vmid = client.get_free_vmid()

        interface0 = rg_data.proxmox_net_device.add_net_device(str(vmid))
        vm_to_create = {
            "vmid": vmid,
            "name": vm_resource.get_name_k8s_format(),
            "memory": vm_resource.flavor.memory_mb,
            "cores": vm_resource.flavor.vcpu_count,
            "sockets": 1,
            "cpu": vm_resource.flavor.vcpu_type,
            "scsihw": "virtio-scsi-single",
            "tags": "nfvcl",  # If you want add more tags, you have to separate them with ";"
            "agent": 1
        }
        vm_to_create[interface0] = f"virtio,bridge={rg_data.proxmox_vnet[vm_resource.management_network]},firewall=0" if vm_resource.management_network in rg_data.proxmox_vnet.keys() else f"virtio,bridge={vm_resource.management_network},firewall=0"

        if client.vim.proxmox_parameters().proxmox_resource_pool:
            vm_to_create["pool"] = client.vim.proxmox_parameters().proxmox_resource_pool

        for net in vm_resource.additional_networks:
            interface = rg_data.proxmox_net_device.add_net_device(str(vmid))
            vm_to_create[interface] = f"virtio,bridge={rg_data.proxmox_vnet[net]},firewall=0" if net in rg_data.proxmox_vnet.keys() else f"virtio,bridge={net},firewall=0"

        if client.version >= IMPORT_URL_VERSION:
            vm_to_create["scsi0"] = f"file={vm_resource.flavor.vm_volume if vm_resource.flavor.vm_volume else client.vm_volume}:0,import-from=local:import/{vm_resource.image.name}.qcow2,iothread=on",
            vm_to_create["boot"] = "order=scsi0"
        else:
            vm_to_create["scsi0"] = f"file={vm_resource.flavor.vm_volume if vm_resource.flavor.vm_volume else client.vm_volume}:0,import-from=local:0/{vm_resource.image.name}.qcow2,iothread=on",
            vm_to_create["boot"] = "order=scsi0"

        client.create_vm(vm_to_create)

        rg_data.proxmox_dict[vm_resource.id] = str(vmid)
        self.save_to_db()
        client.resize_disk(vmid, int(vm_resource.flavor.storage_gb), "scsi0")

        self.__get_macs(client, vmid, vm_resource.resource_group)

        c_init = CloudInit(hostname=vm_resource.name,
                           packages=cloud_init_packages,
                           ssh_authorized_keys=ssh_keys if len(ssh_keys) > 0 else None,
                           runcmd=cloud_init_runcmd)
        c_init.add_user(vm_resource.username, vm_resource.password)

        netwotk_cloud_init: CloudInitNetworkRoot = CloudInitNetworkRoot()

        for mac in rg_data.proxmox_macs[str(vmid)]:
            if mac.net_name == vm_resource.management_network:
                netwotk_cloud_init.add_device(mac.interface_name, mac.mac)
            else:
                netwotk_cloud_init.add_device(mac.interface_name, mac.mac, override=True)

        if client.version >= IMPORT_URL_VERSION:
            client.upload_cnit_iso(
                meta=f"#cloud-config\ninstance-id: {str(uuid.uuid4()).replace('-', '')}",
                user=c_init.build_cloud_config(),
                vendor={},
                network=netwotk_cloud_init.build_cloud_config(),
                filename=f"{vmid}_{vm_resource.resource_group}"
            )
            client.patch_vm_config(
                node=client.get_node_name(),
                vmid=vmid,
                new_config={
                    "ide2": f"{client.images_volume}:iso/{vmid}_{vm_resource.resource_group}.iso,media=cdrom"
                }
            )
        else:
            user_cloud_init_path = f"{client.storage_path}/snippets/user_cloud_init_{vmid}_{vm_resource.resource_group}.yaml"
            network_cloud_init_path = f"{client.storage_path}/snippets/network_cloud_init_{vmid}_{vm_resource.resource_group}.yaml"
            client.load_cloud_init(cloud_init=c_init.build_cloud_config(), cloud_init_path=user_cloud_init_path)
            client.load_cloud_init(cloud_init=netwotk_cloud_init.build_cloud_config(), cloud_init_path=network_cloud_init_path)
            client.patch_vm_config(
                node=client.get_node_name(),
                vmid=vmid,
                new_config={
                    "ide2": f"{vm_resource.flavor.vm_volume if vm_resource.flavor.vm_volume else client.vm_volume}:cloudinit",
                    "cicustom": f"user=local:snippets/user_cloud_init_{vmid}_{vm_resource.resource_group}.yaml,network=local:snippets/network_cloud_init_{vmid}_{vm_resource.resource_group}.yaml"
                }
            )

        client.start_vm(vmid)

        # Loop until qemu-agent is ready
        client.qemu_guest_agent_ready(vmid)
        self.__parse_proxmox_addresses(client, vm_resource, int(vmid))

        # Find the IP to use for configuring the VMte
        if vm_resource.management_network in vm_resource.network_interfaces.keys() and len(vm_resource.network_interfaces[vm_resource.management_network]) > 0:
            vm_resource.access_ip = vm_resource.network_interfaces[vm_resource.management_network][0].fixed.ip
        else:
            raise VirtualizationProviderProxmoxException(f"Error {vm_resource.name} has no an IP assigned")

        # The VM is now created
        vm_resource.created = True

        self.logger.success(f"Creating VM {vm_resource.name} finished")
        self.save_to_db()

    def reboot_vm(self, vm_resource: VmResource, hard: bool = False):
        client = self._get_client(vm_resource.area)
        rg_data = self._get_resource_group_data(client, vm_resource.resource_group)
        self.logger.info(f"Restarting VM {vm_resource.name}")
        if vm_resource.id in rg_data.proxmox_dict.keys():
            vmid = rg_data.proxmox_dict[vm_resource.id]
            client.reboot_vm(vmid, hard)
            self.logger.success(f"VM {vmid} restarted")
        else:
            raise VirtualizationProviderProxmoxException(f"VM {vm_resource.name} not found")

    def check_vm_status(self, vm_resource: VmResource) -> VmStatus:
        """
        Check the status of a VM and SSH connectivity
        Args:
            vm_resource: VM to check

        Returns:
            VmStatus containing vm_name, power_status, and ssh_reachable
        """
        self.logger.info(f"Checking status of VM {vm_resource.name}")

        client = self._get_client(vm_resource.area)
        rg_data = self._get_resource_group_data(client, vm_resource.resource_group)

        if vm_resource.id not in rg_data.proxmox_dict:
            raise VirtualizationProviderProxmoxException(f"VM {vm_resource.name} not found on VIM")

        vmid = rg_data.proxmox_dict[vm_resource.id]

        vm_status_response = client.get_vm_status(vmid)

        proxmox_status = vm_status_response["status"]

        # Map Proxmox status to standardized VmPowerStatus
        if proxmox_status in ["running"]:
            power_status = VmPowerStatus.RUNNING
        elif proxmox_status in ["stopped", "shutoff"]:
            power_status = VmPowerStatus.SHUTOFF
        else:
            # For paused, suspended, or any other unknown states
            power_status = VmPowerStatus.UNKNOWN

        # Check SSH connectivity if VM is running and has an IP
        ssh_reachable = False
        if power_status == VmPowerStatus.RUNNING:
            # Try SSH connection with short timeout (just for testing connectivity)
            ssh_reachable = check_ssh_ready(
                host=vm_resource.access_ip,
                port=22,
                user=vm_resource.username,
                passwd=vm_resource.password,
                logger_override=self.logger
            )

        self.logger.info(f"VM {vm_resource.name} status: proxmox_status={proxmox_status}, mapped_status={power_status}, ssh_reachable={ssh_reachable}")

        return VmStatus(
            vm_name=vm_resource.name,
            power_status=power_status,
            ssh_reachable=ssh_reachable
        )

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        # The parent method checks if the resource is created and throw an exception if not
        super().configure_vm(vm_resource_configuration)
        self.logger.info(f"Configuring VM {vm_resource_configuration.vm_resource.name}")

        configurator_facts = None

        # Different handlers for different configuration types
        if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):  # VmResourceNativeConfiguration
            configurator_facts = configure_vm_ansible(vm_resource_configuration, vm_resource_configuration.resource_group, logger_override=self.logger)

        self.logger.success(f"Configuring VM {vm_resource_configuration.vm_resource.name} finished")
        self.save_to_db()

        return configurator_facts

    def destroy_vm(self, vm_resource: VmResource):
        client = self._get_client(vm_resource.area)
        rg_data = self._get_resource_group_data(client, vm_resource.resource_group)
        self.logger.info(f"Destroying VM {vm_resource.name}")
        if vm_resource.id in rg_data.proxmox_dict.keys():
            vmid = rg_data.proxmox_dict[vm_resource.id]
            client.delete_vm(vmid, vm_resource.resource_group)
            del rg_data.proxmox_dict[vm_resource.id]

    def cleanup_resource_group(self, resource_group: str):
        for vim_name, vim_data in list(self.data.vims.items()):
            rg_data = vim_data.resource_groups.get(resource_group)
            if rg_data is None:
                continue

            client = cast(
                ProxmoxVimClient,
                self.vim_client_pool.get_client_by_vim_name(vim_name, self.provider_vim_type),
            )
            # Delete leftover VMs
            # This shouldn't be needed because VMs are deleted by the generic blueprint cleanup so we'll log a warning
            for vm_resource_id, vm in list(rg_data.proxmox_dict.items()):
                try:
                    self.logger.warning(f"Deleting leftover VM {vm}, something did go wrong in the blueprint deletion")
                    client.delete_vm(vm, resource_group)
                    del rg_data.proxmox_dict[vm_resource_id]
                except Exception as e:
                    self.logger.error(f"Unable to delete leftover VM {vm} on VIM: {e}")

            for vnet in list(rg_data.proxmox_vnet.keys()).copy():
                self.__delete_sdn_vnet(client, vnet, resource_group)

            self._delete_resource_group_data(client, resource_group)
        self.save_to_db()

    def create_net(self, net_resource: NetResource):
        client = self._get_client(net_resource.area)
        self.__create_sdn_vnet(client, net_resource)
        self.save_to_db()
        self.__create_sdn_subnet(client, net_resource)
        self.save_to_db()

    def attach_nets(self, vm_resource: VmResource, nets_name: List[str]) -> List[str]:
        client = self._get_client(vm_resource.area)
        rg_data = self._get_resource_group_data(client, vm_resource.resource_group)
        netplan_interfaces: List[NetplanInterface] = []
        interfaces = []
        vmid = rg_data.proxmox_dict[vm_resource.id]

        for net in nets_name:
            vm_resource.additional_networks.append(net)
            interface = rg_data.proxmox_net_device.add_net_device(str(vmid))
            interfaces.append(interface)
            client.attach_vm_net(vmid, interface, rg_data.proxmox_vnet[net])

        self.__get_macs(client, int(vmid), vm_resource.resource_group)

        for interface in interfaces:
            for mac in rg_data.proxmox_macs[vmid]:
                if mac.hw_interface_name == interface:
                    tmp = NetplanInterface(
                        nic_name=mac.interface_name,
                        mac_address=mac.mac
                    )
                    netplan_interfaces.append(tmp)

        configure_vm_ansible(VmAddNicNetplanConfigurator(vm_resource=vm_resource, nics=netplan_interfaces, resource_group=vm_resource.resource_group), vm_resource.resource_group, logger_override=self.logger)

        self.__parse_proxmox_addresses(client, vm_resource, int(vmid))

        self.logger.success(f"Network {', '.join(nets_name)} attached to VM {vm_resource.name}")
        self.save_to_db()

        ips = []
        for net in nets_name:
            for interface in netplan_interfaces:
                for net_interface in vm_resource.network_interfaces[net]:
                    if net_interface.fixed.interface_name == interface.nic_name and net_interface.fixed.ip not in ips:
                        ips.append(net_interface.fixed.ip)

        return ips

    def __get_macs(self, client: ProxmoxVimClient, vmid: int, resource_group: str):
        config = client.get_vm_config(vmid)
        resource_group_macs = self._get_resource_group_data(client, resource_group).proxmox_macs
        for key in config.keys():
            if re.match("^net[0-9]+$", key):
                tmp = config[key].split(",")
                mac = ProxmoxMac(
                    mac=tmp[0].split("virtio=")[1].strip().lower(),
                    net_name=tmp[1].split("bridge=")[1].strip(),
                    hw_interface_name=key,
                    interface_name=f"eth{key.split('net')[1]}"
                )
                if str(vmid) not in resource_group_macs.keys():
                    resource_group_macs[str(vmid)] = []
                if mac not in resource_group_macs[str(vmid)]:
                    resource_group_macs[str(vmid)].append(mac)

    def __parse_proxmox_addresses(self, client: ProxmoxVimClient, vm_resource: VmResource, vmid: int):
        net_informations = client.get_qemu_agent_interfaces(vmid)
        self.__get_macs(client, vmid, vm_resource.resource_group)
        rg_data = self._get_resource_group_data(client, vm_resource.resource_group)
        for interface in net_informations["result"]:
            mac = interface["hardware-address"]
            for p_mac in rg_data.proxmox_macs[str(vmid)]:
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
                    key = next((key for key, value in rg_data.proxmox_vnet.items() if value == p_mac.net_name), None)

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

    def __get_ips_for_subnets(self, cidr: str) -> Tuple[str, str, str]:
        ips = ipaddress.ip_network(cidr)
        return ips[-2].__format__('s'), ips[2].__format__('s'), ips[-3].__format__('s')

    def __create_sdn_vnet(self, client: ProxmoxVimClient, vnet: NetResource):
        rg_data = self._get_resource_group_data(client, vnet.resource_group)
        identifier = proxmox_sdn_vnet_identifier(vnet.name)
        self.logger.info(f"Creating Vnet {vnet.name}")
        client.create_sdn_vnet(identifier, vnet.name)
        rg_data.proxmox_vnet[vnet.name] = identifier

    def __delete_sdn_vnet(self, client: ProxmoxVimClient, vnet: str, resource_group: str):
        rg_data = self._get_resource_group_data(client, resource_group)
        self.logger.info(f"Deleting Vnet: {vnet}")
        client.delete_sdn_vnet(rg_data.proxmox_vnet[vnet])
        del rg_data.proxmox_vnet[vnet]
        self.logger.success(f"Vnet {vnet} deleted")

    def __create_sdn_subnet(self, client: ProxmoxVimClient, vnet: NetResource):
        rg_data = self._get_resource_group_data(client, vnet.resource_group)
        self.logger.info(f"Creating Vnet Subnet {vnet.cidr}")
        gateway, start_dhcp, end_dhcp = self.__get_ips_for_subnets(vnet.cidr)
        if vnet.allocation_pool:
            start_dhcp = vnet.allocation_pool.start.exploded
            end_dhcp = vnet.allocation_pool.end.exploded
        client.create_sdn_subnet(
            vnet_id=rg_data.proxmox_vnet[vnet.name],
            cidr=vnet.cidr,
            start_dhcp=start_dhcp,
            end_dhcp=end_dhcp,
            gateway=gateway
        )

    def check_networks_exist_on_vim(self, area: int, networks_to_check: set[str], resource_group: Optional[str] = None) -> Tuple[bool, Set[str]]:
        client = self._get_client(area)
        return client.check_networks(networks_to_check)
