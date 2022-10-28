from topology.os_nbi import OSclient
from utils import persistency
from utils.util import *

db = persistency.db()
logger = create_logger('VimTerraformer')


class VimTerraformer:
    def __init__(self, vim: dict):
        """
        vim = {
            name
            external_nets: [ {..., routers = [{}], }]
            provider_nets: []

        }
        """
        if 'name' not in vim:
            raise ValueError('VIM name not provided')

        # credentials should already be stored in the db connection 'vimaccounts'
        self.osClient = OSclient(vim)

    def createRouter(self, router) -> dict:
        if self.osClient.find_router_by_name(router['name']) is not None:
            logger.warn("router {} already existing... deleting and re-creating".format(router['name']))
            self.osClient.delete_router(router['name'])

        if "external_gateway_info" in router:
            _router_id = self.osClient.create_router(
                router['name'],
                additionalProp={"external_gateway_info": router["external_gateway_info"]},
                attach_net_names=router['internal_net']
            )
        else:
            _router_id = self.osClient.create_router(router['name'],
                                                     attach_net_names=router['internal_net'])
        logger.debug(router['internal_net'])
        return {'name': router['name'], 'id': _router_id}

    def createNet(self, net: dict):
        # logger.debug("create net")
        res = {'l2net_id': None, 'l3net_id': None}
        msg = {
            'name': net['name'],
            'external': net['external']
        }
        if net['type'] == 'vlan':
            msg['vid'] = net['vid']

        openstack_l2net = self.osClient.find_network_by_name(net['name'])
        # logger.debug(openstack_l2net)
        # if openstack_l2net is not None and \
        #         openstack_l2net["provider:network_type"] == net['type'] and \
        #         "provider:segmentation_id" in openstack_l2net and \
        #         'vid' in msg and \
        #         openstack_l2net["provider:segmentation_id"] == msg['vid']:
        if openstack_l2net is not None:
            logger.warn("network {} already existing... skipping! If you want to modify the existing net, please"
                        " delete and recreate it".format(net['name']))

            res['l2net_id'] = openstack_l2net['id']
        else:
            openstack_l2net = self.osClient.create_l2network(msg, net['type'])
            res['l2net_id'] = openstack_l2net['id']

        # checking L3 subnet
        openstack_l3nets = self.osClient.list_subnets(l2net_id=openstack_l2net['id'])
        if len(openstack_l3nets) > 0:
            logger.warn("L3 subnet for {} already existing... skipping! If you want to modify the existing net, please"
                        " delete and recreate it".format(net['name']))
            res['l3net_id'] = openstack_l3nets[0]['id']  # taking the first element of the list
        else:
            l3net = self.osClient.create_IPv4_subnet(
                openstack_l2net['id'],
                net['cidr'],
                enable_dhcp=net['dhcp'] if 'dhcp' in net else True,
                gateway=net['gateway'] if 'gateway' in net else "",
                description="",
                allocation_pool=net['allocation_pool'],
                dns_nameservers=[] if 'dns_nameservers' not in net else net['dns_nameservers'],
                host_routes=[] if 'host_routes' not in net else net['host_routes']
            )
            res['l3net_id'] = l3net['id']

        return res

    def delNet(self, net_name):
        if self.osClient.find_network_by_name(net_name) is None:
            logger.warn("network {} not existing".format(net_name))
            return
        return self.osClient.delete_network(network_name=net_name)

    def delRouter(self, router_name):
        if self.osClient.find_router_by_name(router_name) is None:
            logger.warn("router {} not existing".format(router_name))
            return
        return self.osClient.delete_router(name=router_name)
