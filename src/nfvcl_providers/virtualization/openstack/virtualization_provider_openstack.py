import time
from typing import List, Dict, Set, Tuple, Optional, cast

from openstack.compute.v2.server import Server
from openstack.compute.v2.server_interface import ServerInterface
from openstack.network.v2.subnet import Subnet
from pydantic import Field

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_common.cloudinit_builder import CloudInit
from nfvcl_core_models.providers.providers import ProviderData
from nfvcl_core_models.resources import VmResourceAnsibleConfiguration, VmResourceNetworkInterface, \
    VmResourceNetworkInterfaceAddress, VmResource, VmResourceConfiguration, NetResource, VmStatus, VmPowerStatus
from nfvcl_core_models.vim.vim_models import VimTypeEnum
from nfvcl_providers.vim_clients.openstack_vim_client import OpenStackVimClient
from nfvcl_providers.virtualization.common.models.netplan import VmAddNicNetplanConfigurator, NetplanInterface
from nfvcl_providers.virtualization.common.utils import configure_vm_ansible, check_ssh_ready
from nfvcl_providers.virtualization.virtualization_provider_interface import \
    VirtualizationProviderException, \
    VirtualizationProviderInterface, VirtualizationProviderData


class ResourceGroupVirtualizationProviderDataOpenstack(ProviderData):
    os_dict: Dict[str, str] = Field(default_factory=dict)
    flavors: List[str] = Field(default_factory=list)
    networks: List[str] = Field(default_factory=list)
    subnets: List[str] = Field(default_factory=list)


class OpenstackVimProviderData(ProviderData):
    resource_groups: Dict[str, ResourceGroupVirtualizationProviderDataOpenstack] = Field(default_factory=dict)

    def get_resource_group_data(self, resource_group: str) -> ResourceGroupVirtualizationProviderDataOpenstack:
        if resource_group not in self.resource_groups:
            self.resource_groups[resource_group] = ResourceGroupVirtualizationProviderDataOpenstack()
        return self.resource_groups[resource_group]


class VirtualizationProviderDataOpenstack(VirtualizationProviderData):
    vims: Dict[str, OpenstackVimProviderData] = Field(default_factory=dict)

    def get_vim_data(self, vim_name: str) -> OpenstackVimProviderData:
        if vim_name not in self.vims:
            self.vims[vim_name] = OpenstackVimProviderData()
        return self.vims[vim_name]

class VirtualizationProviderOpenstackException(VirtualizationProviderException):
    pass


class VmInfoGathererConfigurator(VmResourceAnsibleConfiguration):
    """
    This configurator is used to gather information about the VM
    """

    def dump_playbook(self) -> str:
        ansible_playbook_builder = AnsiblePlaybookBuilder("Info gathering")

        # Get interface name -> mac address correlation
        # https://unix.stackexchange.com/a/445913
        ansible_playbook_builder.add_run_command_and_gather_output_tasks(
            R"""find /sys/class/net -mindepth 1 -maxdepth 1 ! -name lo -printf "%P: " -execdir cat {}/address \;""",
            "interfaces_mac"
        )

        return ansible_playbook_builder.build()


class VirtualizationProviderOpenstack(VirtualizationProviderInterface):
    provider_vim_type = VimTypeEnum.OPENSTACK
    data: VirtualizationProviderDataOpenstack
    _ATTACHED_NETWORKS_WAIT_TIMEOUT = 60
    _ATTACHED_NETWORKS_WAIT_INTERVAL = 2

    def init(self):
        self.data: VirtualizationProviderDataOpenstack = VirtualizationProviderDataOpenstack()

    def _get_client(self, area: int) -> OpenStackVimClient:
        return cast(OpenStackVimClient, self.get_vim_client(area))

    def _get_resource_group_data(self, client: OpenStackVimClient, resource_group: str) -> ResourceGroupVirtualizationProviderDataOpenstack:
        return self.data.get_vim_data(client.vim.name).get_resource_group_data(resource_group)

    def _delete_resource_group_data(self, client: OpenStackVimClient, resource_group: str):
        return self.data.get_vim_data(client.vim.name).resource_groups.pop(resource_group, None)

    def create_vm(self, vm_resource: VmResource, check_image_hash: bool = False):
        vim_client = self._get_client(vm_resource.area)
        rg_data = self._get_resource_group_data(vim_client, vm_resource.resource_group)
        self.logger.info(f"Creating VM {vm_resource.name}")

        vim_client.pre_creation_checks(vm_resource)

        image = vim_client.prepare_image(vm_resource.image)

        flavor = vim_client.create_get_flavor(vm_resource.flavor, vm_resource.name, rg_data.flavors)

        ssh_keys = []
        ssh_keys.extend(vim_client.vim.ssh_keys or [])
        if vm_resource.flavor.ssh_keys:
            ssh_keys.extend(vm_resource.flavor.ssh_keys)

        c_init = CloudInit(ssh_authorized_keys=ssh_keys)
        c_init.add_user(vm_resource.username, vm_resource.password)
        cloudin = c_init.build_cloud_config()
        self.logger.debug(f"Cloud config:\n{cloudin}")

        # The floating IP should be requested if the VIM require it or if explicitly requested in the blueprint
        auto_ip = vim_client.vim.config.use_floating_ip or vm_resource.require_floating_ip

        # Get the floating ip network name
        floating_ip_net = None
        if auto_ip:
            # TODO instead of raising an exception we should add a way to set the floating ip net in the vim
            floating_ip_net = vim_client.get_floating_ip_network_name()

        # Create the VM and wait for completion
        server_obj: Server = vim_client.client.create_server(
            vm_resource.name,
            image=image,
            flavor=flavor,
            wait=True,
            auto_ip=auto_ip,
            nat_destination=vm_resource.management_network,
            ip_pool=floating_ip_net,
            network=vim_client.network_names_to_ids(vm_resource.get_all_connected_network_names()),
            userdata=cloudin,
            meta={"nfvcl_resource_group": vm_resource.resource_group, "deployed_by": "NFVCL"},
            timeout=vim_client.request_timeout
        )
        # NOTE: Trying to add a tag with the OpenStack SDK will raise a 404 HTTP exception, probably TAGs are not enabled on OS.

        # Don't put code that may crash here, we first need to register the vm_resource server_obj id correlation in the DB
        # This allows to delete a blueprint that crash during the create_vm execution

        # Register the VM in the provider data, this is needed to be able to delete it using only the vm_resource
        rg_data.os_dict[vm_resource.id] = server_obj.id
        self.save_to_db()

        self.__update_net_info_vm(vim_client, vm_resource, server_obj)
        vim_client.disable_port_security_all_ports(vm_resource, server_obj)

        # The VM is now created
        vm_resource.created = True

        self.logger.success(f"Creating VM {vm_resource.name} finished")
        self.save_to_db()

    def reboot_vm(self, vm_resource: VmResource, hard: bool = False):
        vim_client = self._get_client(vm_resource.area)
        rg_data = self._get_resource_group_data(vim_client, vm_resource.resource_group)
        self.logger.info(f"Restarting VM {vm_resource.name}")
        if vm_resource.id not in rg_data.os_dict:
            raise VirtualizationProviderOpenstackException(f"VM {vm_resource.name} not found on VIM, cannot restart")

        server_obj: Server = vim_client.client.get_server(rg_data.os_dict[vm_resource.id])
        if server_obj is None:
            raise VirtualizationProviderOpenstackException(f"VM {vm_resource.name} not found on VIM, cannot restart")

        if hard:
            vim_client.client.compute.reboot_server(server_obj, reboot_type='HARD')
        else:
            vim_client.client.compute.reboot_server(server_obj, reboot_type='SOFT')

        self.logger.success(f"Restarting VM {vm_resource.name} finished")

    def check_vm_status(self, vm_resource: VmResource) -> VmStatus:
        """
        Check the status of a VM and SSH connectivity
        Args:
            vm_resource: VM to check

        Returns:
            VmStatus containing vm_name, power_status, and ssh_reachable
        """
        self.logger.info(f"Checking status of VM {vm_resource.name}")

        vim_client = self._get_client(vm_resource.area)
        rg_data = self._get_resource_group_data(vim_client, vm_resource.resource_group)

        if vm_resource.id not in rg_data.os_dict:
            raise VirtualizationProviderOpenstackException(f"VM {vm_resource.name} not found on VIM")

        server_obj: Server = vim_client.client.get_server(rg_data.os_dict[vm_resource.id])
        if server_obj is None:
            raise VirtualizationProviderOpenstackException(f"VM {vm_resource.name} not found on VIM")

        # Get power status from OpenStack and map to standardized enum
        openstack_status = server_obj.status

        # Map OpenStack status to standardized VmPowerStatus
        if openstack_status in ["ACTIVE"]:
            power_status = VmPowerStatus.RUNNING
        elif openstack_status in ["SHUTOFF", "STOPPED"]:
            power_status = VmPowerStatus.SHUTOFF
        else:
            # For BUILD, REBOOT, HARD_REBOOT, ERROR, PAUSED, SUSPENDED, etc.
            power_status = VmPowerStatus.UNKNOWN

        # Check SSH connectivity if VM is running and has an IP
        ssh_reachable = False
        if power_status == VmPowerStatus.RUNNING and vm_resource.network_interfaces:
            # Try SSH connection with short timeout (just for testing connectivity)
            ssh_reachable = check_ssh_ready(
                host=vm_resource.access_ip,
                port=22,
                user=vm_resource.username,
                passwd=vm_resource.password,
                logger_override=self.logger
            )

        self.logger.info(f"VM {vm_resource.name} status: openstack_status={openstack_status}, mapped_status={power_status}, ssh_reachable={ssh_reachable}")

        return VmStatus(
            vm_name=vm_resource.name,
            power_status=power_status,
            ssh_reachable=ssh_reachable
        )

    def __update_net_info_vm(self, vim_client: OpenStackVimClient, vm_resource: VmResource, server_obj: Server):
        vm_resource.network_interfaces.clear()
        # Getting detailed info about the networks attached to the machine
        subnet_detailed = vim_client.get_network_details(vm_resource.get_all_connected_network_names())
        # Parse the OS output and create a structured network_interfaces dictionary
        self.__parse_os_addresses(vm_resource, server_obj.addresses, subnet_detailed)

        # Find the IP to use for configuring the VM, floating if present or the fixed one from the management interface if not
        mgt_interface = vm_resource.network_interfaces[vm_resource.management_network][0]
        if mgt_interface.floating:
            vm_resource.access_ip = mgt_interface.floating.ip
        else:
            vm_resource.access_ip = mgt_interface.fixed.ip

        # Run an Ansible playbook to gather information
        self.__gather_info_from_vm(vm_resource)

    def __wait_for_server_networks(self, vim_client: OpenStackVimClient, server_id: str, network_names: List[str]) -> Server:
        deadline = time.monotonic() + min(vim_client.request_timeout, self._ATTACHED_NETWORKS_WAIT_TIMEOUT)
        missing_networks = set(network_names)

        while time.monotonic() <= deadline:
            server_obj: Server = vim_client.client.get_server(server_id)
            if server_obj is None:
                raise VirtualizationProviderOpenstackException(f"VM with id {server_id} not found on VIM")

            missing_networks = {net for net in network_names if not server_obj.addresses.get(net)}
            if not missing_networks:
                return server_obj

            time.sleep(self._ATTACHED_NETWORKS_WAIT_INTERVAL)

        raise VirtualizationProviderOpenstackException(
            f"Attached networks {sorted(missing_networks)} did not appear on VM with id {server_id}"
        )

    def attach_nets(self, vm_resource: VmResource, nets_name: List[str]) -> List[str]:
        vim_client = self._get_client(vm_resource.area)
        rg_data = self._get_resource_group_data(vim_client, vm_resource.resource_group)
        server_obj: Server = vim_client.client.get_server(rg_data.os_dict[vm_resource.id])
        if server_obj is None:
            raise VirtualizationProviderOpenstackException(f"VM {vm_resource.name} not found on VIM")

        new_interfaces: List[ServerInterface] = []

        to_attach: List[str] = []
        ips: List[str] = []
        for net in nets_name:
            if net not in server_obj.addresses and net not in to_attach:
                to_attach.append(net)
            else:
                self.logger.warning(f"Network {net} already attached, skipping")

        # If there are no network to attach return
        if len(to_attach) == 0:
            self.logger.warning(f"No new network will be attached to VM {vm_resource.name}")
            return []

        for net in to_attach:
            # Get the OS SDK network object
            network = vim_client.get_network(net)
            if network is None:
                raise VirtualizationProviderOpenstackException(f"Network {net} not found on VIM")
            # Connect the network to the instance
            new_server_interface: ServerInterface = vim_client.client.compute.create_server_interface(rg_data.os_dict[vm_resource.id], net_id=network.id)
            self.logger.debug(f"OS network '{net}' attached to VM {vm_resource.name}")
            # Add the network to the VmResource object
            vm_resource.additional_networks.append(net)
            new_interfaces.append(new_server_interface)

        server_obj = self.__wait_for_server_networks(vim_client, rg_data.os_dict[vm_resource.id], to_attach)
        self.__update_net_info_vm(vim_client, vm_resource, server_obj)
        vim_client.disable_port_security_all_ports(vm_resource, server_obj)

        nics: List[NetplanInterface] = []
        for net in new_interfaces:
            net_intf = vm_resource.get_network_interface_by_fixed_mac(net.mac_addr)
            if net_intf is None:
                raise VirtualizationProviderOpenstackException(
                    f"Attached interface with MAC {net.mac_addr} not found on VM {vm_resource.name}"
                )
            nics.append(NetplanInterface(nic_name=net_intf.fixed.interface_name, mac_address=net.mac_addr))
            ips.append(net_intf.fixed.ip)

        configure_vm_ansible(
            VmAddNicNetplanConfigurator(
                vm_resource=vm_resource,
                nics=nics,
                resource_group=vm_resource.resource_group,
            ),
            vm_resource.resource_group,
            logger_override=self.logger,
        )
        self.logger.success(f"Networks {to_attach} attached to VM {vm_resource.name}")
        self.save_to_db()

        return ips

    def create_net(self, net_resource: NetResource):
        vim_client = self._get_client(net_resource.area)
        rg_data = self._get_resource_group_data(vim_client, net_resource.resource_group)
        self.logger.info(f"Creating NET {net_resource.name}")

        network, subnet = vim_client.create_network(net_resource)

        rg_data.subnets.append(subnet.id)
        rg_data.networks.append(network.id)
        self.save_to_db()

        self.logger.success(f"Creating NET {net_resource.name} finished")

    def __gather_info_from_vm(self, vm_resource: VmResource):
        self.logger.info("Starting VM info gathering")

        facts = configure_vm_ansible(VmInfoGathererConfigurator(vm_resource=vm_resource, resource_group=vm_resource.resource_group), vm_resource.resource_group, logger_override=self.logger)

        mac_name_dict = {}

        interfaces_mac: str = facts["interfaces_mac"]
        for interface_line in interfaces_mac.strip().splitlines():
            interface_line_splitted = interface_line.split(": ")
            # Skip if the interface doesn't have a mac address
            if len(interface_line_splitted) != 2:
                continue
            name = interface_line_splitted[0].strip()
            mac = interface_line_splitted[1].strip()
            mac_name_dict[mac] = name

        for network_interfaces_list in vm_resource.network_interfaces.values():
            for value in network_interfaces_list:
                value.fixed.interface_name = mac_name_dict[value.fixed.mac]
                if value.floating:
                    value.floating.interface_name = mac_name_dict[value.floating.mac]

        self.logger.info("Ended VM info gathering")

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
        vim_client = self._get_client(vm_resource.area)
        rg_data = self._get_resource_group_data(vim_client, vm_resource.resource_group)
        self.logger.info(f"Destroying VM {vm_resource.name}")
        if vm_resource.id in rg_data.os_dict:
            try:
                vim_client.client.delete_server(rg_data.os_dict[vm_resource.id], wait=True, timeout=vim_client.request_timeout)
                rg_data.os_dict.pop(vm_resource.id)
            except Exception as e:
                self.logger.error(f"Unable to delete VM {vm_resource.name} on VIM: {e}")
                raise VirtualizationProviderOpenstackException(f"Unable to delete VM {vm_resource.name} on VIM: {e}") from e
        else:
            self.logger.warning(f"Unable to find VM id for resource '{vm_resource.id}' with name '{vm_resource.name}', manually check on VIM")
        self.logger.success(f"Destroying VM {vm_resource.name} finished")
        self.save_to_db()

    def cleanup_resource_group(self, resource_group: str):
        for vim_name, vim_data in list(self.data.vims.items()):
            rg_data = vim_data.resource_groups.get(resource_group)
            if rg_data is None:
                continue

            vim_client = cast(
                OpenStackVimClient,
                self.vim_client_pool.get_client_by_vim_name(vim_name, self.provider_vim_type),
            )
            # Delete leftover VMs
            # This shouldn't be needed because VMs are deleted by the generic blueprint cleanup so we'll log a warning
            for vm in rg_data.os_dict.values():
                try:
                    self.logger.warning(f"Deleting leftover VM {vm}, something did go wrong in the blueprint deletion")
                    vim_client.client.delete_server(vm, wait=True, timeout=vim_client.request_timeout)
                except Exception as e:
                    self.logger.error(f"Unable to delete leftover VM {vm} on VIM: {e}")
            self._delete_resource_group_data(vim_client, resource_group)
            # Delete flavors
            for flavor_name in rg_data.flavors:
                vim_client.client.delete_flavor(flavor_name)
            # Delete subnets
            for subnet_id in rg_data.subnets:
                vim_client.client.delete_subnet(subnet_id)
            # Delete networks
            for network_id in rg_data.networks:
                vim_client.client.delete_network(network_id)
        self.save_to_db()


    def __parse_os_addresses(self, vm_resource: VmResource, addresses, subnet_details: Dict[str, Subnet]):
        for network_name, network_info in addresses.items():
            fixed = None
            floating = None
            for address in network_info:
                if address["OS-EXT-IPS:type"] == "fixed":
                    fixed = VmResourceNetworkInterfaceAddress(ip=address["addr"], mac=address["OS-EXT-IPS-MAC:mac_addr"], cidr=subnet_details[network_name].cidr)
                if address["OS-EXT-IPS:type"] == "floating":
                    floating = VmResourceNetworkInterfaceAddress(ip=address["addr"], mac=address["OS-EXT-IPS-MAC:mac_addr"], cidr=subnet_details[network_name].cidr)
                if network_name not in vm_resource.network_interfaces:
                    vm_resource.network_interfaces[network_name] = []
            vm_resource.network_interfaces[network_name].append(VmResourceNetworkInterface(fixed=fixed, floating=floating))

    def check_networks_exist_on_vim(self, area: int, networks_to_check: set[str], resource_group: Optional[str] = None) -> Tuple[bool, Set[str]]:
        vim_client = self._get_client(area)
        return vim_client.check_networks_exist_on_vim(networks_to_check)
