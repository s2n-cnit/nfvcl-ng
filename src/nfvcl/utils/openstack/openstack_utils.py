from typing import List
from keystoneauth1.exceptions import Unauthorized
from openstack.network.v2.network import Network
from nfvcl.config_templates.openstack.image_manager import get_nfvcl_image_list
from nfvcl.models.openstack.images import ImageRepo
from nfvcl.models.vim import VimModel
from nfvcl.topology.topology import build_topology
from nfvcl.utils.log import create_logger
from nfvcl.utils.openstack.openstack_client import OpenStackClient

# Logger
logger = create_logger("OpenStack Client")


def check_openstack_instances(vim_list: List[VimModel]):
    """
    Checks that every VIM in the list are ok. Performed checks:
    - Required images
    - Network existence
    This is not blocking it is just printing what is not ok.
    Args:
        vim_list: the vim list to be checked

    Returns:
        A list of VIM in error state. Prints warnings if something is not ok
    """
    logger.debug("Checking OPENSTACK instances")
    error_list: List[VimModel] = []
    for vim in vim_list:
        # If one of the checks goes wrong, then vim is in error state.
        if (check_images(vim) and check_networks(vim)) is False:
            error_list.append(vim)

    logger.debug("Checking OPENSTACK instances: done")
    return error_list


def check_images(vim: VimModel) -> bool:
    """
    Checks the presence of images in the openstack instance (VIM).
    Args:
        vim: The vim to be checked

    Returns:
        True if the VIM contains all the required images by the NFVCL.
    """
    logger.debug(f"Checking presence of required images on OPENSTACK >{vim.name}<")
    required_images = get_nfvcl_image_list() # Get required images by the nfvcl.

    open_stack_client = OpenStackClient(vim)
    try:
        # Get the image list from openstack for the specific instance
        image_list = open_stack_client.client.list_images()
        for image in image_list:
            # For each image build an image repo object
            image_to_search = ImageRepo(name=image.name, url="")
            # It looks if the image on openstack is present in the required ones.
            if image_to_search in required_images.images:
                # If the image is found remove from the required list
                required_images.images.remove(image_to_search)

        # If some required image has not been found, then the list is not empty and contains the ones missing.
        if len(required_images.images) > 0:
            logger.warning(f"The following images are missing from the OpenStack server {vim.name}: {[img.name for img in required_images.images]}")
            return False

    except Unauthorized as e:
        logger.error(f"The VIM {vim.name} is not working correctly. Error: \n{e}")
        return False

    # If every image is present, return true
    logger.debug(f"All images are present in OpenStack server {vim.name}")
    return True


def check_networks(vim: VimModel) -> bool:
    """
    Checks that all networks declared to be part of a VIM are existing on the VIM.
    Args:
        vim: The vim to be checked (a network list is included in the object)

    Returns:
        True if the VIM
    """
    open_stack_client = OpenStackClient(vim)
    topology = build_topology()

    try:
        # Get the net list from openstack for the specific instance
        openstack_network_list = open_stack_client.client.list_networks()
        network: Network
        for network_name in vim.networks:
            # All net details are found in the topology
            network_to_check = topology.get_network(network_name) # get info from topology
            # It looks for the network in the openstack list
            match_net_on_openstack = [os_net for os_net in openstack_network_list if os_net.name == network_name]

            # TODO check that network cidr, dns, gateway... are the same (topology info vs openstack)

            # If not found len == 0
            if len(match_net_on_openstack) <= 0:
                logger.warning(f"The network {network_to_check} does NOT exist in the OpenStack server {vim.name}")
                return False
    except Unauthorized as e:
        logger.error(f"The VIM {vim.name} is not working correctly. Error: \n{e}")
        return False

    # If all the networks are present
    logger.debug(f"Nets are present in OpenStack server {vim.name}")
    return True
