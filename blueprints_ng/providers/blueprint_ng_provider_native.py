from typing import Dict, List

import openstack
from openstack.compute.v2.server import Server
from openstack.network.v2.port import Port
from blueprints_ng.providers.blueprint_ng_provider_interface import *
from blueprints_ng.resources import VmResourceAnsibleConfiguration, VmResourceNativeConfiguration, VmResourceNetworkInterface, VmResourceNetworkInterfaceAddress


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
        image = self.conn.get_image(vm_resource.image.name)

        # Find a flavor with at least 512M of RAM
        flavor = self.conn.get_flavor("big")

        cloudin = """
        #cloud-config
        manage_etc_hosts: true
        password: ubuntu
        chpasswd: { expire: False }
        ssh_pwauth: 1
        """

        networks = [vm_resource.management_network]
        networks.extend(vm_resource.additional_networks)

        server_obj: Server = self.conn.create_server(vm_resource.name, image=image, flavor=flavor, wait=True, auto_ip=vm_resource.require_floating_ip, network=networks, userdata=cloudin)
        print("######################################################################")
        print(server_obj.access_ipv4)

        self.__parse_os_addresses(vm_resource, server_obj.addresses)
        vm_resource.access_ip = server_obj.access_ipv4

        server_ports: List[Port] = self.conn.list_ports(filters={"device_id": server_obj.id})
        if len(server_ports) != len(networks):
            raise BlueprintsNgProviderNativeException(f"Mismatch in number of request network interface and ports, query: device_id={server_obj.id}")

        for port in server_ports:
            self.__disable_port_security(port.id)

        vm_resource.created = True
        self.data.os_dict[vm_resource.id] = server_obj.id

        print("create_vm end")

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration):
        super().configure_vm(vm_resource_configuration)
        print("configure_vm begin")

        # if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):
        #     dumped = vm_resource_configuration.dump_playbook()
        #     print(f"Sending dumped playbook to ansible: {dumped}")
        # elif isinstance(vm_resource_configuration, VmResourceNativeConfiguration):
        #     print("Running the requested code")
        #     vm_resource_configuration.run_code()
        #     print("Finished running code")

        print("configure_vm end")

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
