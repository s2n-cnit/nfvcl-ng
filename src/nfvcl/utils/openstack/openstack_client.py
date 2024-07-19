from pathlib import Path

from openstack.image.v2.image import Image
from nfvcl.models.openstack.images import ImageRepo
from nfvcl.models.vim import VimModel
from nfvcl.utils.log import create_logger
import openstack
import os
from openstack.connection import Connection
from nfvcl.utils.util import render_file_from_template_to_file

# Logger
logger = create_logger("OpenStack Client")
# Client list for the singleton pattern. One client for each OS cloud instance
clients: dict = {}

def _get_client(cloud_name: str) -> Connection:
    """
    It creates and connects a client to an OPENSTACK instance.
    Allows having ONLY ONE instance for each OS cloud.
    The configuration file path must be set in 'os.environ["OS_CLIENT_CONFIG_FILE"]' before calling this method.
    Args:
        cloud_name: The name of the cloud instance, to be used for the singleton pattern.

    Returns:
        The OS client for interacting with the cloud. (Openstack.connection.Connection)
    """
    if cloud_name in clients.keys():
        return clients[cloud_name]
    else:
        client = openstack.connect(cloud=cloud_name)
        clients[cloud_name] = client
        return client



class OpenStackClient:
    """
    Client that interacts with an Openstack instance
    """
    client: Connection

    def __init__(self, vim: VimModel):
        """
        Create an Openstack client
        Args:
            vim: the vim on witch the client is build.
        """
        filepath = render_file_from_template_to_file(Path("src/nfvcl/config_templates/openstack/clouds.yaml"), vim.model_dump(), prefix_to_name=vim.name)
        os.environ["OS_CLIENT_CONFIG_FILE"] = str(filepath.absolute())
        # Get the client using a singleton pattern
        self.client = _get_client(vim.name)


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




