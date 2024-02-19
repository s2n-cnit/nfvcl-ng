import tempfile
from typing import Dict, List

import ansible_runner
import openstack
from openstack.compute.v2.server import Server
from openstack.network.v2.port import Port

from blueprints_ng.providers.blueprint_ng_provider_interface import *
from blueprints_ng.providers.utils import create_ansible_inventory, wait_for_ssh_to_be_ready
from blueprints_ng.resources import VmResourceAnsibleConfiguration, VmResourceNetworkInterface, \
    VmResourceNetworkInterfaceAddress


class BlueprintNGProviderDataNative(BlueprintNGProviderData):
    os_dict: Dict[str, str] = {}


class BlueprintsNgProviderNativeException(BlueprintNGProviderException):
    pass


class BlueprintsNgProviderNative(BlueprintNGProviderInterface):

    def __init__(self):
        super().__init__()
        self.data: BlueprintNGProviderDataNative = BlueprintNGProviderDataNative()
        # Initialize and turn on debug logging
        openstack.enable_logging(debug=False)

        # Initialize connection
        self.conn = openstack.connect(cloud='oslab')

    def create_vm(self, vm_resource: VmResource):
        print("create_vm begin")
        # Get the image to use for the instance, TODO download it from url if not on server (see OS utils)
        image = self.conn.get_image(vm_resource.image.name)

        # TODO create a new flavor
        flavor = self.conn.get_flavor("big")

        # TODO build the cloudinit config, create a generic builder
        cloudin = """
        #cloud-config
        manage_etc_hosts: true
        password: ubuntu
        chpasswd: { expire: False }
        ssh_pwauth: 1
        """

        # Create a list with all the network interfaces that need to be added to the new VM
        networks = [vm_resource.management_network]
        networks.extend(vm_resource.additional_networks)

        # Create the VM and wait for completion
        server_obj: Server = self.conn.create_server(vm_resource.name, image=image, flavor=flavor, wait=True, auto_ip=vm_resource.require_floating_ip, network=networks, userdata=cloudin)
        print("######################################################################")
        print(server_obj.access_ipv4)

        # Parse the OS output and create a structured network_interfaces dictionary
        self.__parse_os_addresses(vm_resource, server_obj.addresses)

        # Find the IP to use for configuring the VM, floating if present or the fixed one from the management interface if not
        if server_obj.access_ipv4 and len(server_obj.access_ipv4) > 0:
            vm_resource.access_ip = server_obj.access_ipv4
        else:
            vm_resource.access_ip = vm_resource.network_interfaces[vm_resource.management_network].fixed.ip

        # Disable port security on very port
        server_ports: List[Port] = self.conn.list_ports(filters={"device_id": server_obj.id})
        if len(server_ports) != len(networks):
            raise BlueprintsNgProviderNativeException(f"Mismatch in number of request network interface and ports, query: device_id={server_obj.id}")
        for port in server_ports:
            self.__disable_port_security(port.id)

        # The VM is now created
        vm_resource.created = True

        # Register the VM in the provider data, this is needed to be able to delete it using only the vm_resource id
        self.data.os_dict[vm_resource.id] = server_obj.id

        print("create_vm end")

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration):
        # The parent method checks if the resource is created and throw an exception if not
        super().configure_vm(vm_resource_configuration)
        print("configure_vm begin")

        # Different handlers for different configuration types
        if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):  #VmResourceNativeConfiguration
            self.__configure_vm_ansible(vm_resource_configuration)

        print("configure_vm end")

    def __configure_vm_ansible(self, vm_resource_configuration: VmResourceAnsibleConfiguration):
        tmp_playbook = tempfile.NamedTemporaryFile(mode="w")
        tmp_inventory = tempfile.NamedTemporaryFile(mode="w")
        tmp_private_data_dir = tempfile.TemporaryDirectory()

        # Write the inventory and playbook to files
        tmp_inventory.write(create_ansible_inventory(vm_resource_configuration.vm_resource.access_ip, vm_resource_configuration.vm_resource.username, vm_resource_configuration.vm_resource.password))
        tmp_playbook.write(vm_resource_configuration.dump_playbook())
        tmp_playbook.flush()
        tmp_inventory.flush()

        # container_volume_mounts = [
        #     f"{tmp_playbook.name}:{tmp_playbook.name}",
        #     f"{tmp_inventory.name}:{tmp_inventory.name}",
        #     f"{tmp_private_data_dir.name}:{tmp_private_data_dir.name}",
        # ]

        # Wait for SSH to be ready, this is needed because sometimes cloudinit is still not finished and the server doesn't allow password connections
        wait_for_ssh_to_be_ready(
            vm_resource_configuration.vm_resource.access_ip,
            22,
            vm_resource_configuration.vm_resource.username,
            vm_resource_configuration.vm_resource.password,
            300,
            5
        )

        # Run the playbook, TODO better integration, error checking, logging, ...
        r = ansible_runner.run(
            playbook=tmp_playbook.name,
            inventory=tmp_inventory.name,
            private_data_dir=tmp_private_data_dir.name,
            # process_isolation_executable="docker",
            # process_isolation=True,
            # container_volume_mounts=container_volume_mounts
        )

        # Close the tmp files, this will delete them
        tmp_playbook.close()
        tmp_inventory.close()
        tmp_private_data_dir.cleanup()

    def destroy_vm(self, vm_resource: VmResource):
        print("start destroy_vm")
        self.conn.delete_server(self.data.os_dict[vm_resource.id], wait=True)
        print("end destroy_vm")

    def install_helm_chart(self):
        print("install_helm_chart")

    def update_values_helm_chart(self):
        print("update_values_helm_chart")

    def uninstall_helm_chart(self):
        print("uninstall_helm_chart")

    def __parse_os_addresses(self, vm_resource: VmResource, addresses):
        for network_name, network_info in addresses.items():
            fixed = None
            floating = None
            for address in network_info:
                if address["OS-EXT-IPS:type"] == "fixed":
                    fixed = VmResourceNetworkInterfaceAddress(ip=address["addr"], mac=address["OS-EXT-IPS-MAC:mac_addr"])
                if address["OS-EXT-IPS:type"] == "floating":
                    floating = VmResourceNetworkInterfaceAddress(ip=address["addr"], mac=address["OS-EXT-IPS-MAC:mac_addr"])
            vm_resource.network_interfaces[network_name] = VmResourceNetworkInterface(fixed=fixed, floating=floating)

    def __disable_port_security(self, port_id):
        try:
            return self.conn.update_port(port_id, port_security_enabled=False, security_groups=[])
        except Exception as e:
            raise e
