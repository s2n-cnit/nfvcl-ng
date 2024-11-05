import hashlib
from typing import List, Dict

import requests
from openstack.compute.v2.flavor import Flavor
from openstack.compute.v2.server import Server
from openstack.compute.v2.server_interface import ServerInterface
from openstack.connection import Connection
from openstack.exceptions import ForbiddenException
from openstack.network.v2.network import Network
from openstack.network.v2.port import Port
from openstack.network.v2.subnet import Subnet

from nfvcl.blueprints_ng.ansible_builder import AnsiblePlaybookBuilder
from nfvcl.blueprints_ng.cloudinit_builder import CloudInit
from nfvcl.blueprints_ng.providers.virtualization.common.models.netplan import VmAddNicNetplanConfigurator, \
    NetplanInterface
from nfvcl.blueprints_ng.providers.virtualization.common.utils import configure_vm_ansible
from nfvcl.blueprints_ng.providers.virtualization.virtualization_provider_interface import \
    VirtualizationProviderException, \
    VirtualizationProviderInterface, VirtualizationProviderData
from nfvcl.blueprints_ng.resources import VmResourceAnsibleConfiguration, VmResourceNetworkInterface, \
    VmResourceNetworkInterfaceAddress, VmResource, VmResourceConfiguration, NetResource, VmResourceFlavor, VmResourceImage
from nfvcl.models.vim import VimModel
from nfvcl.utils.openstack.openstack_client import OpenStackClient


class VirtualizationProviderDataOpenstack(VirtualizationProviderData):
    os_dict: Dict[str, str] = {}
    flavors: List[str] = []
    networks: List[str] = []
    subnets: List[str] = []


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


os_clients_dict: Dict[int, OpenStackClient] = {}


def get_os_client_from_vim(vim: VimModel, area: int):
    global os_clients_dict

    if area not in os_clients_dict:
        os_clients_dict[area] = OpenStackClient(vim)

    return os_clients_dict[area]


class VirtualizationProviderOpenstack(VirtualizationProviderInterface):
    vim: VimModel
    os_client: OpenStackClient
    conn: Connection
    vim_need_floating_ip: bool

    def init(self):
        self.data: VirtualizationProviderDataOpenstack = VirtualizationProviderDataOpenstack()
        self.vim = self.topology.get_vim_from_area_id_model(self.area)
        self.os_client = get_os_client_from_vim(self.vim, self.area)
        self.conn = self.os_client.client
        self.vim_need_floating_ip = self.vim.config.use_floating_ip

    def __create_image_from_url(self, vm_image: VmResourceImage):
        image_attrs = {
            'name': vm_image.name,
            'disk_format': 'qcow2',
            'container_format': 'bare',
            'visibility': 'public',
        }
        try:
            image = self.conn.image.create_image(**image_attrs)
        except ForbiddenException as exc:
            self.logger.warning("Cannot create public image, trying again with private")
            image_attrs['visibility'] = "private"
            image = self.conn.image.create_image(**image_attrs)

        self.conn.image.import_image(image, method="web-download", uri=vm_image.url)
        self.conn.wait_for_image(image)
        return image

    def _pre_creation_checks(self, vm_resource: VmResource):
        """
        Check if everything on the OpenStack server is as expected
        Args:
            vm_resource: VmResource

        Returns: True if everything is as expected, False otherwise
        """
        for net in vm_resource.get_all_connected_network_names():
            if self.os_client.get_network(net) is None:
                raise VirtualizationProviderOpenstackException(f"Network >{net}< not found on vim")

    def __get_checksum(self, vm_image: VmResourceImage) -> str:
        self.logger.debug(f"Downloading {vm_image.url} image on NFVCL machine to compute its hash 512...")
        response = requests.get(vm_image.url, stream=True)

        if response.status_code == 200:
            file_hash = hashlib.sha512(response.content).hexdigest()
            self.logger.debug(f"Downloading of {vm_image.url} finished")
            return file_hash
        else:
            self.logger.error(f"Failed to download file. Status code: {response.status_code}")
            raise ValueError("The URL is not valid")

    def __prepare_image(self, vm_image: VmResourceImage):
        """
        Download the image if it is not present on the VIM.
        If the image requires to check if the hash 512 coincides, the nfvcl downloads the file and compare the hash: if it
        differs than it creates a new image with a different name.
        N.B. The old image cannot be deleted since it can be used by other VMs
        Args:
            vm_image: The image to be prepared

        Returns:
            The existing image on the VIM.
        """
        image = self.conn.get_image(vm_image.name)
        if image is None:
            if vm_image.url:
                self.logger.info(f"Image {vm_image.name} not found on VIM, downloading from {vm_image.url}")
                image = self.__create_image_from_url(vm_image)
                self.logger.info(f"Image {vm_image.name} download completed")
            else:
                raise VirtualizationProviderOpenstackException(f"Image >{vm_image.name}< not found")
        elif vm_image.check_sha512sum and vm_image.check_sha512sum:
            os_remote_image = self.conn.get_image(vm_image.name)
            os_remote_image_hash512 = os_remote_image.hash_value
            new_image_hash512 = self.__get_checksum(vm_image)
            # If sha does not coincide, image needs to be updated
            if new_image_hash512 != os_remote_image_hash512:
                # WE NEED TO CHANGE NAME SINCE WE CANNOT DELETE THE OLD ONE BECAUSE IT CAN BE USED BY OTHER INSTANCES
                # We are using the HASH to compute the new name soo we can identify if it is already present
                vm_image.name = vm_image.name+new_image_hash512[0:12]
                image = self.conn.get_image(vm_image.name)
                if image is None:
                    self.logger.info(f"Updated image {vm_image.name} not found on VIM, downloading on VIM from {vm_image.url}")
                    image = self.__create_image_from_url(vm_image)
                    self.logger.info(f"Image {vm_image.name} download completed on VIM")
                else:
                    self.logger.info("Updated image has been found on VIM, download will be skipped")
            else:
                self.logger.info(f"Image {vm_image.name} on Openstack sha512 coincides with the one of the remote image")
        return image

    def create_vm(self, vm_resource: VmResource, check_image_hash: bool = False):
        self.logger.info(f"Creating VM {vm_resource.name}")

        self._pre_creation_checks(vm_resource)

        image = self.__prepare_image(vm_resource.image)

        flavor: Flavor = self.create_get_flavor(vm_resource.flavor, vm_resource.name)

        c_init = CloudInit(ssh_authorized_keys=self.vim.ssh_keys)
        c_init.add_user(vm_resource.username, vm_resource.password)
        cloudin = c_init.build_cloud_config()
        self.logger.debug(f"Cloud config:\n{cloudin}")

        # The floating IP should be requested if the VIM require it or if explicitly requested in the blueprint
        auto_ip = self.vim_need_floating_ip or vm_resource.require_floating_ip

        # Get the floating ip network name
        floating_ip_net = None
        if auto_ip:
            float_ip_nets: List[Network] = self.conn.get_external_ipv4_floating_networks()
            if len(float_ip_nets) == 1:
                floating_ip_net = float_ip_nets[0].name
            else:
                # TODO instead of raising an exception we should add a way to set the floating ip net in the vim
                raise VirtualizationProviderOpenstackException("Multiple floating ip networks found")

        # Create the VM and wait for completion
        server_obj: Server = self.conn.create_server(
            vm_resource.name,
            image=image,
            flavor=flavor,
            wait=True,
            auto_ip=auto_ip,
            nat_destination=vm_resource.management_network,
            ip_pool=floating_ip_net,
            network=self.os_client.network_names_to_ids(vm_resource.get_all_connected_network_names()),
            userdata=cloudin
        )

        # Don't put code that may crash here, we first need to register the vm_resource server_obj id correlation in the DB
        # This allows to delete a blueprint that crash during the create_vm execution

        # Register the VM in the provider data, this is needed to be able to delete it using only the vm_resource
        self.data.os_dict[vm_resource.id] = server_obj.id
        self.save_to_db()

        self.__update_net_info_vm(vm_resource, server_obj)
        self.__disable_port_security_all_ports(vm_resource, server_obj)

        # The VM is now created
        vm_resource.created = True

        self.logger.success(f"Creating VM {vm_resource.name} finished")
        self.save_to_db()

    def __update_net_info_vm(self, vm_resource: VmResource, server_obj: Server):
        vm_resource.network_interfaces.clear()
        # Getting detailed info about the networks attached to the machine
        subnet_detailed = self.__get_network_details(vm_resource.get_all_connected_network_names())
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

    def __disable_port_security_all_ports(self, vm_resource: VmResource, server_obj: Server):
        server_ports: List[Port] = self.conn.list_ports(filters={"device_id": server_obj.id})
        if len(server_ports) != len(vm_resource.get_all_connected_network_names()):
            raise VirtualizationProviderOpenstackException(f"Mismatch in number of request network interface and ports, query: device_id={server_obj.id}")

        if getattr(vm_resource, 'require_port_security_disabled', None):  # TODO remove in future. For now to maintain back compatibility
            if vm_resource.require_port_security_disabled:
                for port in server_ports:
                    self.__disable_port_security(self.conn, port.id)

    def attach_nets(self, vm_resource: VmResource, nets_name: List[str]) -> List[str]:
        server_obj: Server = self.conn.get_server(self.data.os_dict[vm_resource.id])

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
            network = self.os_client.get_network(net)
            # Connect the network to the instance
            new_server_interface: ServerInterface = self.conn.compute.create_server_interface(self.data.os_dict[vm_resource.id], net_id=network.id)
            self.logger.debug(f"OS network '{net}' attached to VM {vm_resource.name}")
            # Add the network to the VmResource object
            vm_resource.additional_networks.append(net)
            new_interfaces.append(new_server_interface)

        self.__update_net_info_vm(vm_resource, server_obj)
        self.__disable_port_security_all_ports(vm_resource, server_obj)

        nics: List[NetplanInterface] = []
        for net in new_interfaces:
            net_intf = vm_resource.get_network_interface_by_fixed_mac(net.mac_addr)
            nics.append(NetplanInterface(nic_name=net_intf.fixed.interface_name, mac_address=net.mac_addr))
            ips.append(net_intf.fixed.ip)

        configure_vm_ansible(VmAddNicNetplanConfigurator(vm_resource=vm_resource, nics=nics), self.blueprint_id, logger_override=self.logger)
        self.logger.success(f"Networks {to_attach} attached to VM {vm_resource.name}")
        self.save_to_db()

        return ips

    def create_net(self, net_resource: NetResource):
        self.logger.info(f"Creating NET {net_resource.name}")

        if self.os_client.get_network(net_resource.name):
            raise VirtualizationProviderOpenstackException(f"Network {net_resource.name} already exist")
        if self.conn.list_subnets(filters={"cidr": net_resource.cidr, "name": net_resource.name, "project_id": self.os_client.project_id}):
            raise VirtualizationProviderOpenstackException(f"Subnet with cidr {net_resource.cidr} already exist")

        network: Network = self.conn.create_network(net_resource.name, port_security_enabled=False)
        subnet: Subnet = self.conn.create_subnet(
            network.id,
            cidr=net_resource.cidr,
            enable_dhcp=True,
            disable_gateway_ip=True
        )

        self.data.subnets.append(subnet.id)
        self.data.networks.append(network.id)

        self.logger.success(f"Creating NET {net_resource.name} finished")

    def create_get_flavor(self, requested_flavor: VmResourceFlavor, vm_name: str) -> Flavor:
        """
        Get a flavor if flavor name is present, create it if a flavor with that name does not exist.
        Otherwise, it creates a flavor, from specification, if not already present.
        Args:
            requested_flavor: Flavor to be get/created.
            vm_name: The VM name used to name the flavor if the flavor name is not present.
        Returns:
            The flavor on the VIM
        """
        # If a flavor name is specified, try to use that one.
        if requested_flavor.name is not None:
            found_flavor_on_vim = self.conn.get_flavor(requested_flavor.name)
            # If not found, try to create it with specifications.
            if found_flavor_on_vim is None:
                flavor: Flavor = self.conn.create_flavor(
                    requested_flavor.name,
                    requested_flavor.memory_mb,
                    requested_flavor.vcpu_count,
                    requested_flavor.storage_gb,
                    is_public=True
                )
                return flavor
            return found_flavor_on_vim
        # If no name was given, create it by specifications
        else:
            flavor_name = f"Flavor_{vm_name}"
            # If present in local flavor list -> Already created
            if flavor_name in self.data.flavors:
                flavor: Flavor = self.conn.get_flavor(flavor_name)
                if flavor is None:
                    raise VirtualizationProviderOpenstackException(f"Flavor '{flavor_name}' should be present but is None")
            # Otherwise, creates the flavor
            else:
                flavor: Flavor = self.conn.create_flavor(
                    flavor_name,
                    requested_flavor.memory_mb,
                    requested_flavor.vcpu_count,
                    requested_flavor.storage_gb,
                    is_public=False
                )
                project = self.conn.get_project(self.vim.vim_tenant_name)
                self.conn.add_flavor_access(flavor.id, project['id'])
                self.data.flavors.append(flavor_name)
            return flavor

    def __gather_info_from_vm(self, vm_resource: VmResource):
        self.logger.info(f"Starting VM info gathering")

        facts = configure_vm_ansible(VmInfoGathererConfigurator(vm_resource=vm_resource), self.blueprint_id, logger_override=self.logger)

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

        self.logger.info(f"Ended VM info gathering")

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
        if vm_resource.id in self.data.os_dict:
            self.conn.delete_server(self.data.os_dict[vm_resource.id], wait=True)
        else:
            self.logger.warning(f"Unable to find VM id for resource '{vm_resource.id}' with name '{vm_resource.name}', manually check on VIM")
        self.logger.success(f"Destroying VM {vm_resource.name} finished")
        self.save_to_db()

    def final_cleanup(self):
        # Delete flavors
        for flavor_name in self.data.flavors:
            self.conn.delete_flavor(flavor_name)
        # Delete subnets
        for subnet_id in self.data.subnets:
            self.conn.delete_subnet(subnet_id)
        # Delete networks
        for network_id in self.data.networks:
            self.conn.delete_network(network_id)

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

    def __disable_port_security(self, conn: Connection, port_id):
        try:
            return conn.update_port(port_id, port_security_enabled=False, security_groups=[])
        except Exception as e:
            raise e

    def __get_network_details(self, network_names: List[str]) -> Dict[str, Subnet]:
        """
        Given the network names, it retrieves the details of the first subnet of every network
        Args:
            network_names: The network names

        Returns:
            A list containing the details of every FIRST subnet of the netowrk
        """
        subnet_detail_list = {}
        for network_name in network_names:
            network_detail: Network = self.os_client.get_network(network_name)
            subnet_detail_list[network_name] = self.conn.get_subnet(network_detail.subnet_ids[0])
        return subnet_detail_list
