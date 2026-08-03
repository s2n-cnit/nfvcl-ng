import concurrent.futures
import hashlib
from typing import Optional, List, Dict, Tuple, Set

import httpx
import requests
from keystoneauth1.exceptions import Unauthorized
from openstack.compute.v2.flavor import Flavor
from openstack.compute.v2.server import Server
from openstack.exceptions import SDKException, ForbiddenException
from openstack.image.v2.image import Image
from openstack.network.v2.network import Network
from openstack.network.v2.port import Port
from openstack.network.v2.subnet import Subnet

from nfvcl_providers.vim_clients.vim_client import VimClient
from nfvcl_core_models.openstack.images import ImageRepo
from nfvcl_core_models.resources import VmResource, VmResourceFlavor, VmResourceImage, NetResource
from nfvcl_core_models.vim.vim_models import VimModel
import openstack
from openstack.connection import Connection

DEFAULT_OPENSTACK_TIMEOUT = 180  # See openstack/cloud/_compute.py

class OpenStackVimClient(VimClient):
    """
    Client that interacts with an Openstack instance
    """
    client: Connection
    project_id: str
    user_id: str

    def __init__(self, vim: VimModel):
        """
        Create an Openstack client
        Args:
            vim: the vim on witch the client is build.
        """
        super().__init__(vim)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(self._connect_and_setup)
            future.result(timeout=15)
        except concurrent.futures.TimeoutError as exc:
            raise ConnectionError(f"Connection to OpenStack at {vim.vim_url} timed out after 15 seconds") from exc
        finally:
            executor.shutdown(wait=False)

    def _connect_and_setup(self):
        self.client = openstack.connect(
            auth_url=self.vim.vim_url,
            project_name=self.vim.openstack_parameters().project_name,
            username=self.vim.vim_user,
            password=self.vim.vim_password,
            region_name=self.vim.openstack_parameters().region_name,
            user_domain_name=self.vim.openstack_parameters().user_domain_name,
            project_domain_name=self.vim.openstack_parameters().project_domain_name,
            app_name='NFVCL',
            app_version='0.4.0', # TODO: get the version from the package
        )
        try:
            self.client.authorize()
        except (Unauthorized, SDKException) as e:
            raise Unauthorized(f"Error while connecting to Openstack (Credentials may be invalid): {e}") from e
        self.user_id = self.client.session.get_user_id()
        user_projects = self.client.identity.user_projects(self.user_id)
        # We don't use anymore self.client.identity.find_project(vim.openstack_parameters.project_name, vim.openstack_parameters.project_domain_name).id
        # because it is using http://10.10.0.206/openstack-keystone/v3/projects?domain_id=users witch requires to be administrator of the cluster.
        # Instead, http://10.10.0.206/openstack-keystone/v3/users/13de4bfd017746daabe4131377614a55/projects (used by .user_projects) requires to be an admin of the project.

        matching_projects = [project for project in user_projects if project.name == self.vim.openstack_parameters().project_name]
        if not matching_projects:
            raise ValueError(f"Project {self.vim.openstack_parameters().project_name} not found for user {self.user_id}. Check if user has been added to the project or if the project name is correct.")
        if len(matching_projects) > 1:
            self.logger.warning(f"Multiple projects found with name {self.vim.openstack_parameters().project_name}. Using the first one.")
        self.project_id = matching_projects[0].id

    def close(self):
        if self.closed:
            return
        client = getattr(self, "client", None)
        if client is not None:
            client.close()
        super().close()

    def get_available_networks(self) -> Dict[str, Network]:
        """
        Get all available networks that the user can access.
        Returns:
            Dict[str, Network]: A dictionary of network names and their corresponding Network objects.
        """
        shared_networks = list(self.client.network.networks(shared=True))
        project_networks = list(self.client.network.networks(project_id=self.project_id))
        all_networks: Dict[str, Network] = {network.name: network for network in shared_networks}
        all_networks.update({network.name: network for network in project_networks})
        return all_networks

    def get_network(self, network_name: str) -> Optional[Network]:
        """
        Get a OS network from the ones that the project can access
        Args:
            network_name: The name of the network

        Returns: The Network object or None if a network with the given name does not exist.
        """
        all_networks = self.get_available_networks()
        return all_networks[network_name] if network_name in all_networks else None

    def network_names_to_ids(self, network_names: List[str]) -> List[str]:
        """
        Convert a list of network names to a list of network ids.
        Args:
            network_names: Names of the networks to convert.
        Returns: List of network ids.
        """
        id_list = []
        all_networks = self.get_available_networks()
        for network_name in network_names:
            id_list.append(all_networks[network_name].id)
        return id_list

    @property
    def request_timeout(self) -> int:
        return DEFAULT_OPENSTACK_TIMEOUT if self.vim.vim_timeout is None else self.vim.vim_timeout

    def pre_creation_checks(self, vm_resource: VmResource):
        for net in vm_resource.get_all_connected_network_names():
            if self.get_network(net) is None:
                raise ValueError(f"Network >{net}< not found on vim")

    def create_image_from_url(self, vm_image: VmResourceImage):
        image_attrs = {
            'name': vm_image.name,
            'disk_format': 'qcow2',
            'container_format': 'bare',
            'visibility': 'public',
        }
        try:
            image = self.client.image.create_image(**image_attrs)
        except ForbiddenException:
            self.logger.warning("Cannot create public image, trying again with private")
            image_attrs['visibility'] = "private"
            image = self.client.image.create_image(**image_attrs)

        try:
            with httpx.Client(timeout=10.0) as http_client:
                http_client.head(vm_image.url, follow_redirects=True).raise_for_status()
        except httpx.HTTPError as exc:
            self.client.image.delete_image(image)
            raise ValueError(f"Image URL >{vm_image.url}< is not reachable: {exc}") from exc

        self.client.image.import_image(image, method="web-download", uri=vm_image.url)
        self.client.wait_for_image(image)
        return image

    def get_image_checksum(self, vm_image: VmResourceImage) -> str:
        self.logger.debug(f"Downloading {vm_image.url} image on NFVCL machine to compute its hash 512...")
        response = requests.get(vm_image.url, stream=True)

        if response.status_code == 200:
            file_hash = hashlib.sha512(response.content).hexdigest()
            self.logger.debug(f"Downloading of {vm_image.url} finished")
            return file_hash
        self.logger.error(f"Failed to download file. Status code: {response.status_code}")
        raise ValueError("The URL is not valid")

    def prepare_image(self, vm_image: VmResourceImage):
        image = self.client.get_image(vm_image.name)
        if image is None:
            if vm_image.url:
                self.logger.info(f"Image {vm_image.name} not found on VIM, downloading from {vm_image.url}")
                image = self.create_image_from_url(vm_image)
                self.logger.info(f"Image {vm_image.name} download completed")
            else:
                raise ValueError(f"Image >{vm_image.name}< not found")
        elif vm_image.check_sha512sum and vm_image.check_sha512sum:
            os_remote_image = self.client.get_image(vm_image.name)
            os_remote_image_hash512 = os_remote_image.hash_value
            new_image_hash512 = self.get_image_checksum(vm_image)
            if new_image_hash512 != os_remote_image_hash512:
                vm_image.name = vm_image.name + new_image_hash512[0:12]
                image = self.client.get_image(vm_image.name)
                if image is None:
                    self.logger.info(f"Updated image {vm_image.name} not found on VIM, downloading on VIM from {vm_image.url}")
                    image = self.create_image_from_url(vm_image)
                    self.logger.info(f"Image {vm_image.name} download completed on VIM")
                else:
                    self.logger.info("Updated image has been found on VIM, download will be skipped")
            else:
                self.logger.info(f"Image {vm_image.name} on Openstack sha512 coincides with the one of the remote image")
        return image

    def get_floating_ip_network_name(self) -> str:
        float_ip_nets: List[Network] = self.client.get_external_ipv4_floating_networks()
        if len(float_ip_nets) == 1:
            return float_ip_nets[0].name
        raise ValueError("Multiple floating ip networks found")

    def create_get_flavor(self, requested_flavor: VmResourceFlavor, vm_name: str, created_flavors: List[str]) -> Flavor:
        if requested_flavor.name is not None:
            found_flavor_on_vim = self.client.get_flavor(requested_flavor.name)
            if found_flavor_on_vim is None:
                return self.client.create_flavor(
                    requested_flavor.name,
                    requested_flavor.memory_mb,
                    requested_flavor.vcpu_count,
                    requested_flavor.storage_gb,
                    is_public=True
                )
            return found_flavor_on_vim

        flavor_name = f"Flavor_{vm_name}"
        flavor: Flavor = self.client.get_flavor(flavor_name)
        if flavor_name in created_flavors and flavor is None:
            raise ValueError(f"Flavor '{flavor_name}' should be present but is None")
        if not flavor:
            flavor = self.client.create_flavor(
                flavor_name,
                requested_flavor.memory_mb,
                requested_flavor.vcpu_count,
                requested_flavor.storage_gb,
                is_public=False
            )
            self.client.add_flavor_access(flavor.id, self.project_id)
            created_flavors.append(flavor_name)
        return flavor

    def create_network(self, net_resource: NetResource) -> Tuple[Network, Subnet]:
        if self.get_network(net_resource.name):
            raise ValueError(f"Network {net_resource.name} already exist")
        if self.client.list_subnets(filters={"cidr": net_resource.cidr, "name": net_resource.name, "project_id": self.project_id}):
            raise ValueError(f"Subnet with cidr {net_resource.cidr} already exist")

        allocation_pools = None
        if net_resource.allocation_pool:
            allocation_pools = [{"start": net_resource.allocation_pool.start.exploded, "end": net_resource.allocation_pool.end.exploded}]

        network: Network = self.client.create_network(net_resource.name, port_security_enabled=False)
        subnet: Subnet = self.client.create_subnet(
            network.id,
            cidr=net_resource.cidr,
            enable_dhcp=True,
            disable_gateway_ip=True,
            allocation_pools=allocation_pools
        )
        return network, subnet

    def get_network_details(self, network_names: List[str]) -> Dict[str, Subnet]:
        subnet_detail_list = {}
        for network_name in network_names:
            network_detail: Network = self.get_network(network_name)
            subnet_detail_list[network_name] = self.client.get_subnet(network_detail.subnet_ids[0])
        return subnet_detail_list

    def disable_port_security(self, port_id: str):
        return self.client.update_port(port_id, port_security_enabled=False, security_groups=[])

    def disable_port_security_all_ports(self, vm_resource: VmResource, server_obj: Server):
        server_ports: List[Port] = self.client.list_ports(filters={"device_id": server_obj.id})
        if len(server_ports) != len(vm_resource.get_all_connected_network_names()):
            raise ValueError(f"Mismatch in number of request network interface and ports, query: device_id={server_obj.id}")

        if getattr(vm_resource, 'require_port_security_disabled', None):
            if vm_resource.require_port_security_disabled:
                for port in server_ports:
                    self.disable_port_security(port.id)

    def check_networks_exist_on_vim(self, networks_to_check: set[str]) -> Tuple[bool, Set[str]]:
        networks_tmp = self.get_available_networks()
        networks = set(networks_tmp.keys())
        return networks_to_check.issubset(networks), networks_to_check.difference(networks)

    def find_image(self, image_name: str) -> Image | None:
        """
        Find image on openstack given the name
        Args:
            image_name: The name of the image

        Returns:
            The image if found, None otherwise
        """
        return self.client.image.find_image(image_name, ignore_missing=True)

    def delete_image(self, image: Image):
        """
        Delete an image from openstack
        Args:
            image: The image to be deleted, can be retrieved with

        Returns:
            The deleted image if found.
        """
        return self.client.delete_image(image)

    def create_and_download_image(self, image: ImageRepo):
        """
        This method is used to create an image (QCOW2 format) on openstack and then download it from the repo.
        Args:
            image: The image object is containin the image name and the image URL.

        Returns:
            The result of image downloading from the given URL.
        """
        os_image = self.create_image(image.name)
        return self.web_download_image(os_image, image.url)

    def create_image(self, image_name: str) -> Image | None:
        """
        Create an image, without uploading the binary image, on Openstack.
        The binary image needs to be uploaded or imported from a URL.
        Args:
            image_name: The name to be given at the openstack image.

        Returns:

        """
        # Build the image attributes and create the image.
        image_attrs = {
            'name': image_name,
            'disk_format': 'qcow2',
            'container_format': 'bare',
            'visibility': 'public',
        }
        image = self.client.image.create_image(**image_attrs)

        return image


    def web_download_image(self, image: Image, uri):
        """
        For an existing image it starts importing the binary image from a URL
        Args:
            image: The created image (openstack.image.v2.image.Image)
            uri: example_value = 'https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64-disk-kvm.img'

        Returns:
            The result of image importing.
        """
        imported = self.client.image.import_image(image, method="web-download", uri=uri)
        return imported
