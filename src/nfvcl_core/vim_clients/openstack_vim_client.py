from typing import Optional, List, Dict

from openstack.image.v2.image import Image
from openstack.network.v2.network import Network

from nfvcl_core.vim_clients.vim_client import VimClient
from nfvcl_core_models.openstack.images import ImageRepo
from nfvcl_core_models.vim.vim_models import VimModel
import openstack
from openstack.connection import Connection

class OpenStackVimClient(VimClient):
    """
    Client that interacts with an Openstack instance
    """
    client: Connection
    project_id: str

    def __init__(self, vim: VimModel):
        """
        Create an Openstack client
        Args:
            vim: the vim on witch the client is build.
        """
        super().__init__(vim)
        self.client = openstack.connect(
            auth_url=vim.vim_url,
            project_name=vim.openstack_parameters.project_name,
            username=vim.vim_user,
            password=vim.vim_password,
            region_name=vim.openstack_parameters.region_name,
            user_domain_name=vim.openstack_parameters.user_domain_name,
            project_domain_name=vim.openstack_parameters.project_domain_name,
            app_name='NFVCL',
            app_version='0.4.0', # TODO: get the version from the package
        )

        self.project_id = self.client.identity.find_project(vim.openstack_parameters.project_name).id

    def close(self):
        super().close()
        self.client.close()

    def get_available_networks(self) -> Dict[str, Network]:
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
