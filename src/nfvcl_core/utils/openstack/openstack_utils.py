from typing import List
from keystoneauth1.exceptions import Unauthorized

from nfvcl_core.vim_clients.openstack_vim_client import OpenStackVimClient
from nfvcl_core_models.topology_models import TopologyModel
from nfvcl_core_models.vim.vim_models import VimModel
from nfvcl_core.utils.log import create_logger

# Logger
logger = create_logger("OpenStack Client")


def check_openstack_instances(topology: TopologyModel, vim_list: List[VimModel]) -> List[VimModel]:
    """
    Checks that every VIM in the list are ok. Performed checks:
    - Required images
    - Network existence
    This is not blocking it is just printing what is not ok.
    Args:
        topology: Topology
        vim_list: the vim list to be checked

    Returns:
        A list of VIM in error state. Prints warnings if something is not ok
    """
    logger.debug("Checking OPENSTACK instances")
    error_list: List[VimModel] = []
    for vim in vim_list:
        # If one of the checks goes wrong, then vim is in error state.
        if check_networks(topology, vim) is False:
            error_list.append(vim)

    logger.debug("Checking OPENSTACK instances: done")
    return error_list


def check_networks(topology: TopologyModel, vim: VimModel) -> bool:
    """
    Checks that all networks declared to be part of a VIM are existing on the VIM.
    Args:
        topology: Topology
        vim: The vim to be checked (a network list is included in the object)

    Returns:
        True if the VIM
    """
    # TODO this should work but we should instead request the client from the VimClientsManager
    open_stack_client = OpenStackVimClient(vim)

    try:
        # Get the net list from openstack for the specific instance
        openstack_network_list = open_stack_client.client.list_networks()
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
