from models.config_model import NFVCLConfigModel
from utils.util import get_nfvcl_config
from utils import persistency
from nfvo.osm_nbi_util import NbiUtil
from neutronclient.v2_0 import client as neutron_client
from typing import Optional
from keystoneauth1.identity import v3
from keystoneauth1 import session
import ipaddress
import logging

nfvcl_config: NFVCLConfigModel = get_nfvcl_config()

nbiUtil = NbiUtil(username=nfvcl_config.osm.username, password=nfvcl_config.osm.password,
                  project=nfvcl_config.osm.project, osm_ip=nfvcl_config.osm.host, osm_port=nfvcl_config.osm.port)
db = persistency.DB()

logger = logging.getLogger('keystoneauth')
ch = logging.StreamHandler()
ch.setLevel(logging.WARN)
# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# add formatter to ch
ch.setFormatter(formatter)
logger.addHandler(ch)
# logger.setLevel(logging.WARN)



def get_nova_credentials(os_account: dict) -> dict:
    if os_account is None:
        raise ValueError('VIM is None')
    return {
        'username': os_account['vim_user'],
        'password': os_account['vim_password'],
        'auth_url': os_account['vim_url'],
        'project_name': os_account['vim_tenant_name'],
        'user_domain_id': 'default' if 'user_domain_id' not in os_account else os_account['user_domain_id'],
        'project_domain_id': 'default' if 'project_domain_id' not in os_account else os_account['project_domain_id'],
    }


def authenticate(os_account: dict):
    try:
        auth = v3.Password(**get_nova_credentials(os_account))
        return session.Session(auth=auth)
    except Exception as e:
        raise e


class OSclient:
    def __init__(self, os_account: dict):
        self.credentials = get_nova_credentials(os_account)
        self.session = session.Session(auth=v3.Password(**self.credentials))
        self.neutron_client = neutron_client.Client(session=self.session)

    def allowed_address_pairs(self, port_id, allowed_pairs=None):
        try:
            if allowed_pairs is None:
                allowed_pairs = [{'ip_address': '0.0.0.0/0'}]
            return self.neutron_client.update_port(port_id, {'port': {'allowed_address_pairs': allowed_pairs}})
        except Exception as e:
            raise e

    def disable_port_security(self, port_id):
        try:
            return self.neutron_client.update_port(port_id, {'port': {'port_security_enabled': False}})
        except Exception as e:
            raise e

    def create_l2network(self, args, net_type: str):
        msg_body = {'name': args['name'], 'admin_state_up': True}
        if net_type == "vlan":
            msg_body.update({
                "provider:network_type": "vlan",
                "provider:physical_network": "physnet1",
                "provider:segmentation_id": args['vid']
            })
        if "external" in args and isinstance(args["external"], bool):
            msg_body.update({
                "router:external": args["external"]
            })
        net = self.neutron_client.create_network(body={'network': msg_body})
        return net['network']

    def create_IPv4_subnet(self, net_id: str, cidr: str, enable_dhcp=False, gateway=None, description="",
                           allocation_pool=None, dns_nameservers=None, host_routes=None):
        if allocation_pool is None:
            allocation_pool = []
        if dns_nameservers is None:
            dns_nameservers = []
        if host_routes is None:
            host_routes = []

        msg = {
            'ip_version': 4,
            'cidr': cidr,
            'network_id': net_id,
            'enable_dhcp': enable_dhcp,
            'allocation_pools': allocation_pool,  # allocation pool should be [{start: ip1, end: ip2}, ...]
            'dns_nameservers': dns_nameservers,
            'host_routes': host_routes,
            'description': description
        }

        if gateway:
            msg['gateway_ip'] = gateway

        subnet = self.neutron_client.create_subnet(body={'subnets': [msg]})
        logger.debug(subnet)
        return subnet['subnets'][0]

    def create_network(self, network_name: str, net_ip=None, allocation_pool=None, enable_dhcp=True,
                       dns_nameservers=None, gateway_ip=None, host_routes=None):
        try:
            cidr = ipaddress.IPv4Network(net_ip)
            net = self.neutron_client.create_network(body={'network': {'name': network_name, 'admin_state_up': True}})

            subnet_msg = {
                'cidr': cidr,
                'ip_version': 4,
                'network_id': net['network']['id'],
                'enable_dhcp': enable_dhcp,
                'gateway_ip': gateway_ip
            }
            # allocation pool should be [{start: ip1, end: ip2}, ...]
            if allocation_pool:
                subnet_msg['allocation_pools'] = allocation_pool
            if dns_nameservers:
                subnet_msg['dns_nameservers'] = dns_nameservers
            if host_routes:
                subnet_msg['host_routes'] = host_routes

            subnet = self.neutron_client.create_subnet(body={'subnets': [subnet_msg]})
            return {'net': net, 'subnet': subnet}
        except Exception as e:
            raise e

    def list_subnets(self, l2net_id: Optional[str] = None) -> list:

        body = {'network_id': l2net_id} if l2net_id else {}
        try:
            return self.neutron_client.list_subnets(**body)['subnets']
        except Exception as e:
            raise e

    def list_networks(self):
        try:
            return self.neutron_client.list_networks()['networks']
        except Exception as e:
            raise e

    def find_network_by_name(self, net_name: str):
        try:
            return next((item for item in self.neutron_client.list_networks()['networks']
                         if item['name'] == net_name), None)
        except Exception as e:
            raise e

    def find_network_id_by_name(self, net_name: str):
        net = self.find_network_by_name(net_name)
        return net['id'] if net is not None else None

    def delete_network(self, network_name=None, network_id=None):
        if network_name is None and network_id is None:
            raise ValueError('net id and name are None')
        if network_id is None:
            network_id = self.find_network_id_by_name(network_name)
        try:
            # check if there are any ports still connected to this network
            ports = self.list_ports_in_net(network_name, network_id=network_id)
            for p in ports:
                self.delete_port(p['id'])
            self.neutron_client.delete_network(network_id)
            return True
        except Exception as e:
            return e

    def create_router(self, router_name: str, additionalProp=None, attach_net_names=None):
        try:
            request = {'router': {'name': router_name, 'admin_state_up': True}}
            if additionalProp:
                request['router'].update(additionalProp)
            logger.debug(request)
            router = self.neutron_client.create_router(request)
            router_id = router['router']['id']
            router = self.neutron_client.show_router(router_id)
            if attach_net_names:
                for net in attach_net_names:
                    self.connect_router_to_net(router_name, net, router_id=router_id)
            return router_id
        except Exception as e:
            raise e

    def find_router_id_by_name(self, name: str):
        router = self.find_router_by_name(name)
        return None if router is None else router['id']

    def find_router_by_name(self, name: str):
        try:
            return next((item for item in self.neutron_client.list_routers()['routers']
                         if item['name'] == name), None)
        except Exception as e:
            raise e

    def connect_router_to_net(
            self, router_name: str, network_name: str, router_id=None, network_id=None, ip_address=None):
        try:
            if router_id is None:
                router_id = self.find_router_id_by_name(router_name)

            if network_id is None:
                network_id = self.find_network_id_by_name(network_name)

            body_value = {'port': {
                'admin_state_up': True,
                'device_id': router_id,
                'name': 'port_{}'.format(network_name),
                'network_id': network_id
            }}
            if ip_address is not None:
                body_value['port']['fixed_ips'] = [{'ip_address': ip_address}]
            self.neutron_client.create_port(body=body_value)
            return router_id
        except Exception as e:
            raise e

    def delete_router(self, name=None, osid=None):
        if name is None and osid is None:
            raise ValueError('net id and name are None')
        if osid is None:
            osid = self.find_router_id_by_name(name)
        try:
            self.neutron_client.delete_router(osid)
            return True
        except Exception as e:
            return e

    def list_routers(self):
        try:
            return self.neutron_client.list_routers()['networks']
        except Exception as e:
            raise e

    def list_ports_in_net(self, network_name: str, network_id=None):
        try:
            if network_id is None:
                network_id = self.find_router_id_by_name(network_name)
            ports = [item for item in self.neutron_client.list_ports()['ports'] if item['network_id'] == network_id]
            return ports
        except Exception as e:
            raise e

    def delete_port(self, osid: str):
        try:
            self.neutron_client.delete_port(osid)
            return True
        except Exception as e:
            return e

    def create_fip(self, description="", dns_domain="", dns_name="", fixed_ip_address="", floating_ip_address="",
                   name="", port_id="", router_id="", subnet_id=""):
        """
description: The floating IP description.
dns_domain:  The DNS domain.
dns_name:    The DNS name.
fixed_ip_address: The fixed IP address associated with the floating IP. If you intend to associate the floating IP
                  with a fixed IP at creation time, then you must indicate the identifier of the internal port.
                  If an internal port has multiple associated IP addresses, the service chooses the first IP unless you
                  explicitly specify the parameter fixed_ip_address to select a specific IP.
floating_ip_address:    The floating IP address.
name:     Floating IP object doesn’t have name attribute, set ip address to name so that user could find floating IP by
          UUID or IP address using find_ip
floating_network_id:    The ID of the network associated with the floating IP.
port_details:   Read-only. The details of the port that this floating IP associates with. Present if fip-port-details
                extension is loaded. Type: dict with keys: name, network_id, mac_address, admin_state_up, status,
                device_id, device_owner
port_id:    The port ID.
qos_policy_id:  The ID of the QoS policy attached to the floating IP.
project_id:     The ID of the project this floating IP is associated with.
router_id:  The ID of an associated router.
status:     The floating IP status. Value is ACTIVE or DOWN.
subnet_id:  The Subnet ID associated with the floating IP.
        """
        msg = {
            'description': description,
            'fixed_ip_address': fixed_ip_address,
            'floating_ip_address': floating_ip_address,
            'dns_domain': dns_domain,
            'dns_name': dns_name,
            'name': name,
            'port_id': port_id,
            'router_id': router_id,
            'subnet_id': subnet_id
        }
        try:
            fip = self.neutron_client.create_floatingip(body={'floatingip': {msg}})
        except Exception as e:
            return e

        return fip

    def delete_fip(self, fip_id):
        res = self.neutron_client.create_floatingip(fip_id)
        return res
