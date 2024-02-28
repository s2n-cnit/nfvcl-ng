import asyncio
import tempfile
import time
from pathlib import Path
from typing import List

import ansible_runner
import paramiko
from openstack.compute.v2.flavor import Flavor
from openstack.compute.v2.server import Server
from openstack.connection import Connection
from openstack.network.v2.port import Port
from pyhelm3 import Client

from blueprints_ng.cloudinit_builder import CloudInit
from blueprints_ng.providers.blueprint_ng_provider_interface import *
from blueprints_ng.providers.utils import create_ansible_inventory
from blueprints_ng.resources import VmResourceAnsibleConfiguration, VmResourceNetworkInterface, \
    VmResourceNetworkInterfaceAddress
from models.k8s.topology_k8s_model import K8sModel
from rest_endpoints.k8s import get_k8s_cluster_by_area
from topology.topology import build_topology
from utils.openstack.openstack_client import OpenStackClient


class BlueprintNGProviderDataNative(BlueprintNGProviderData):
    os_dict: Dict[str, str] = {}
    flavors: Dict[str, str] = {}
    areas: List[int] = []


class BlueprintsNgProviderNativeException(BlueprintNGProviderException):
    pass


os_connections_dict: Dict[int, Connection] = {}
helm_client_dict: Dict[int, Client] = {}
# TODO find a better way
global_topology = build_topology()


class BlueprintsNgProviderNative(BlueprintNGProviderInterface):
    def __init__(self, blueprint):
        super().__init__(blueprint)
        self.data: BlueprintNGProviderDataNative = BlueprintNGProviderDataNative()
        self.topology = global_topology

    def __get_os_connection_by_area(self, area: int):
        global os_connections_dict

        if area in os_connections_dict:
            return os_connections_dict[area]

        # TODO it only work with one OpenStack instance
        conn: Connection = OpenStackClient(self.topology.get_vim_from_area_id_model(area)).client
        os_connections_dict[area] = conn
        self.data.areas.append(area)
        return conn

    def __get_helm_client_by_area(self, area: int):
        global helm_client_dict

        if area in helm_client_dict:
            return helm_client_dict[area]

        k8s_cluster: K8sModel = get_k8s_cluster_by_area(area)
        k8s_credential_file_path = Path(tempfile.gettempdir(), f"k8s_credential_{k8s_cluster.name}")
        with open(k8s_credential_file_path, mode="w") as k8s_credential_file:
            k8s_credential_file.write(k8s_cluster.credentials)

        helm_client = Client(kubeconfig=k8s_credential_file_path)
        helm_client_dict[area] = helm_client
        return helm_client

    def create_vm(self, vm_resource: VmResource):
        os_conn = self.__get_os_connection_by_area(vm_resource.area)

        self.logger.info(f"Creating VM {vm_resource.name}")
        # Get the image to use for the instance, TODO download it from url if not on server (see OS utils)
        image = os_conn.get_image(vm_resource.image.name)

        flavor_str = f"{vm_resource.flavor.memory_mb}-{vm_resource.flavor.vcpu_count}-{vm_resource.flavor.storage_gb}"
        if flavor_str in self.data.flavors:
            flavor = os_conn.get_flavor(self.data.flavors[flavor_str])
        else:
            flavor_name = f"{self.blueprint.id}_flavor_{len(self.data.flavors) + 1}"
            flavor: Flavor = os_conn.create_flavor(
                flavor_name,
                vm_resource.flavor.memory_mb,
                vm_resource.flavor.vcpu_count,
                vm_resource.flavor.storage_gb,
            )
            self.data.flavors[flavor_str] = flavor_name

        cloudin = CloudInit(password=vm_resource.password).build_cloud_config()
        self.logger.debug(f"Cloud config:\n{cloudin}")

        # Create a list with all the network interfaces that need to be added to the new VM
        networks = [vm_resource.management_network]
        networks.extend(vm_resource.additional_networks)

        # Create the VM and wait for completion
        server_obj: Server = os_conn.create_server(vm_resource.name, image=image, flavor=flavor, wait=True, auto_ip=vm_resource.require_floating_ip, network=networks, userdata=cloudin)

        # Parse the OS output and create a structured network_interfaces dictionary
        self.__parse_os_addresses(vm_resource, server_obj.addresses)

        # Find the IP to use for configuring the VM, floating if present or the fixed one from the management interface if not
        if server_obj.access_ipv4 and len(server_obj.access_ipv4) > 0:
            vm_resource.access_ip = server_obj.access_ipv4
        else:
            vm_resource.access_ip = vm_resource.network_interfaces[vm_resource.management_network].fixed.ip

        # Disable port security on very port
        server_ports: List[Port] = os_conn.list_ports(filters={"device_id": server_obj.id})
        if len(server_ports) != len(networks):
            raise BlueprintsNgProviderNativeException(f"Mismatch in number of request network interface and ports, query: device_id={server_obj.id}")
        for port in server_ports:
            self.__disable_port_security(os_conn, port.id)

        # The VM is now created
        vm_resource.created = True

        # Register the VM in the provider data, this is needed to be able to delete it using only the vm_resource id
        self.data.os_dict[vm_resource.id] = server_obj.id

        self.logger.success(f"Creating VM {vm_resource.name} finished")
        self.blueprint.to_db()

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration):
        # The parent method checks if the resource is created and throw an exception if not
        super().configure_vm(vm_resource_configuration)
        self.logger.info(f"Configuring VM {vm_resource_configuration.vm_resource.name}")

        # Different handlers for different configuration types
        if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):  # VmResourceNativeConfiguration
            self.__configure_vm_ansible(vm_resource_configuration)

        self.logger.success(f"Configuring VM {vm_resource_configuration.vm_resource.name} finished")
        self.blueprint.to_db()

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
        self.__wait_for_ssh_to_be_ready(
            vm_resource_configuration.vm_resource.access_ip,
            22,
            vm_resource_configuration.vm_resource.username,
            vm_resource_configuration.vm_resource.password,
            300,
            5
        )

        def my_status_handler(data, runner_config):
            self.logger.info(f"[ANSIBLE] Current status: {data['status']}")

        def my_event_handler(data):
            # TODO change logging type if error
            block = data["stdout"].strip()
            if len(block) > 0:
                lines = block.split("\n")
                for line in lines:
                    self.logger.debug(f"[ANSIBLE] {line.strip()}")

        # Delete known_hosts to prevent error, nothing else seems working
        # TODO find a better way
        Path(Path.home(), ".ssh/known_hosts").unlink(missing_ok=True)

        # https://github.com/ansible/ansible-runner/issues/398#issuecomment-948885921

        # Run the playbook, TODO better integration, error checking, logging, ...
        ansible_runner_result = ansible_runner.run(
            playbook=tmp_playbook.name,
            inventory=tmp_inventory.name,
            private_data_dir=tmp_private_data_dir.name,
            status_handler=my_status_handler,
            event_handler=my_event_handler,
            quiet=True
        )

        # Close the tmp files, this will delete them
        tmp_playbook.close()
        tmp_inventory.close()
        tmp_private_data_dir.cleanup()

        if ansible_runner_result.status == "failed":
            raise BlueprintsNgProviderNativeException("Error running ansible configurator")

    def destroy_vm(self, vm_resource: VmResource):
        os_conn = self.__get_os_connection_by_area(vm_resource.area)

        self.logger.info(f"Destroying VM {vm_resource.name}")
        os_conn.delete_server(self.data.os_dict[vm_resource.id], wait=True)
        self.logger.success(f"Destroying VM {vm_resource.name} finished")
        self.blueprint.to_db()

    def install_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        helm_client = self.__get_helm_client_by_area(helm_chart_resource.area)

        self.logger.info(f"Installing Helm chart {helm_chart_resource.name}")

        chart = asyncio.run(helm_client.get_chart(
            helm_chart_resource.get_chart_converted(),
            repo=helm_chart_resource.repo,
            version=helm_chart_resource.version
        ))
        print(chart.metadata.name, chart.metadata.version)
        # print(asyncio.run(chart.readme()))

        # Install or upgrade a release
        revision = asyncio.run(helm_client.install_or_upgrade_release(
            helm_chart_resource.name.lower(),
            chart,
            values,
            namespace=helm_chart_resource.namespace.lower(),
            atomic=True,
            wait=True
        ))
        print(
            revision.release.name,
            revision.release.namespace,
            revision.revision,
            str(revision.status)
        )
        releases = asyncio.run(helm_client.list_releases(all=True, all_namespaces=True))
        for release in releases:
            revision = asyncio.run(release.current_revision())
            print(release.name, release.namespace, revision.revision, str(revision.status))

        self.logger.success(f"Installing Helm chart {helm_chart_resource.name} finished")
        self.blueprint.to_db()

    def update_values_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        helm_client = self.__get_helm_client_by_area(helm_chart_resource.area)

        chart = asyncio.run(helm_client.get_chart(
            helm_chart_resource.get_chart_converted(),
            repo=helm_chart_resource.repo,
            version=helm_chart_resource.version
        ))
        print(chart.metadata.name, chart.metadata.version)
        # print(asyncio.run(chart.readme()))

        # Install or upgrade a release
        revision = asyncio.run(helm_client.install_or_upgrade_release(
            helm_chart_resource.name.lower(),
            chart,
            values,
            namespace=helm_chart_resource.namespace.lower(),
            atomic=True,
            wait=True
        ))
        print(
            revision.release.name,
            revision.release.namespace,
            revision.revision,
            str(revision.status)
        )
        self.blueprint.to_db()

    def uninstall_helm_chart(self, helm_chart_resource: HelmChartResource):
        helm_client = self.__get_helm_client_by_area(helm_chart_resource.area)

        asyncio.run(helm_client.uninstall_release(
            helm_chart_resource.name.lower(),
            namespace=helm_chart_resource.namespace.lower(),
            wait=True
        ))
        self.blueprint.to_db()

    def configure_hardware(self, hardware_resource_configuration: HardwareResourceConfiguration):
        print("start configure_hardware")
        print("end configure_hardware")

    def final_cleanup(self):
        # Delete flavors from every area used by the blueprint
        for area in self.data.areas:
            os_conn = self.__get_os_connection_by_area(area)
            for flavor_str, flavor_name in self.data.flavors.items():
                os_conn.delete_flavor(flavor_name)

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

    def __disable_port_security(self, conn: Connection, port_id):
        try:
            return conn.update_port(port_id, port_security_enabled=False, security_groups=[])
        except Exception as e:
            raise e
