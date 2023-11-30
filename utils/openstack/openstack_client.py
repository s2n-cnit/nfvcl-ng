from openstack.image.v2.image import Image
from models.openstack.images import ImageRepo
from models.vim import VimModel
from utils.log import create_logger
import openstack
import os
from openstack.connection import Connection
from utils.util import render_file_from_template

# Logger
logger = create_logger("OpenStack Client")
# Client list for singleton pattern. One client for each OS cloud instance
clients: dict = {}

def get_client(cloud_name: str) -> Connection:
    """
    Allow to have ONLY one instance for each OS cloud.
    Args:
        cloud_name: The name of the cloud instance

    Returns:
        The OS client for interacting with the cloud. (openstack.connection.Connection)
    """
    if cloud_name in clients.keys():
        return clients[cloud_name]
    else:
        client = openstack.connect(cloud=cloud_name)
        clients[cloud_name] = client
        return client

class OpenStackClient:
    """
    Client that interact with an Openstack instance
    """
    client: Connection

    def __init__(self, vim: VimModel):
        """
        Create an Openstack client
        Args:
            vim: the vim on witch the client is build.
        """
        filepath = render_file_from_template("config_templates/openstack/clouds.yaml", vim.model_dump())
        os.environ["OS_CLIENT_CONFIG_FILE"] = filepath
        # Get the client using singleton pattern
        self.client = get_client(vim.name)


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
            The delete image if found.
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
        image = self.create_image(image.name)
        return self.web_download_image(image, image.url)

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




