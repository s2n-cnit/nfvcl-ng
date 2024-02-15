from typing import List
from configurators.flex_configurator import Configurator_Flex
from ..models import VyOSRouterNetworkEndpoints, VyOSSourceNATRule, VyOSDestNATRule
import secrets
from utils.log import create_logger
from ..models.vyos_firewall_rules_model import VyOSFirewallRule, VyOSFirewallRuleSecond

logger = create_logger('VyOS Conf')


class Configurator_VyOS(Configurator_Flex):
    router_area_id: int
    network_endpoints: VyOSRouterNetworkEndpoints
    admin_username: str
    admin_password: str

    def __init__(self, area_id: int, nsd_name: str, m_id: int, blue_id: str,
                 network_endpoints: VyOSRouterNetworkEndpoints = None, admin_username: str = 'vyos',
                 admin_password: str = 'vyos'):
        # NOTE: args is the tac obj within blue.conf
        self.network_endpoints = network_endpoints
        self.router_area_id = area_id
        self.type = "VyOS"
        self.admin_username = admin_username
        self.admin_password = admin_password
        super(Configurator_VyOS, self).__init__(nsd_name, m_id, blue_id)

        # Do not set as second arg an empty list, or it will override the playbook vars
        self.addPlaybook('blueprints/blue_vyos/config_scripts/playbook_empty_vyos.yaml')

        self.add_vyos_config_vars(username=self.admin_username, password=self.admin_password)
        logger.info("Configurator_VyOs created")

    def initial_configuration(self):
        """
        Perform initial configuration for VyOS router, this includes:
        - Set up a name to management interface
        - Setup data interfaces
        - Configure loopback interface
        - Add a Vyos Info task to retrieve information from VyOS in the callback
        - Add Vyos Info task to retrieve information from VyOS in the callback
        """
        self.setup_man_interface_descr()
        self.setup_data_interfaces()
        self.setup_loopback_ip()
        self.add_vyos_info_task()

    def setup_man_interface_descr(self):
        """
        Create a task to be executed for configuring the management interface on the router.
        Remember that a configurator is assigned to only a router.
        The task is added to the playbook of the configurator.
        """
        lines = ["set interface ethernet eth0 description 'Management Network'"]
        self.add_vyos_config_task('Description of eth0', 'vyos.vyos.vyos_config', lines)

    def setup_loopback_ip(self):
        """
        Create a task to be executed for configuring the loopback interface on the router. Remember that a configurator
        is assigned to only a router.
        The task is added to the playbook of the configurator.
        """
        lines = []
        loopback_ipaddr = "10.200." + str(self.router_area_id) + ".1/32"
        lines.append("set interfaces loopback lo address {}".format(loopback_ipaddr))
        self.add_vyos_config_task('Configuring loopback', 'vyos.vyos.vyos_config', lines)

    def setup_data_interfaces(self):
        """
        Set up the data interfaces needed for configuring the data interfaces on the router.
        The task is added to the playbook of the configurator.
        """
        lines = []

        interface_index = 1  # STARTING From 1 because management interface is always present and called eth0
        # This code works because vyos create sequential interfaces starting from eth0, eth1, eth2, ..., ethN
        for network in self.network_endpoints.data_nets:
            # Getting prefix length
            prefix_length = network.network.prefixlen
            # Getting the address of the net to be configured on the interface

            interface_address = network.ip_addr.exploded
            # NOTE: the ip address is got by get IP address, but OSM is not reporting netmask! setting /24 as default
            if interface_address is None:
                lines.append("set interfaces ethernet eth{} address dhcp".format(interface_index))
            else:
                lines.append("set interfaces ethernet eth{} address {}/{}".format(interface_index, interface_address,
                                                                                  prefix_length))
            lines.append("set interfaces ethernet eth{} description \'{}\'".format(interface_index, self.blue_id))
            lines.append("set interfaces ethernet eth{} duplex auto".format(interface_index))
            lines.append("set interfaces ethernet eth{} speed auto".format(interface_index))
            # MAX supported MTU is 1450 by OPENSTACK
            lines.append("set interfaces ethernet eth{} mtu 1450".format(interface_index))
            interface_index = interface_index + 1
        self.add_vyos_config_task('Configure DATA Interfaces', 'vyos.vyos.vyos_config', lines)

    def setup_snat_rules(self, rule_list: List[VyOSSourceNATRule]):
        """
        Create a task which will add the instructions to configure a list of SNAT rules to the router.
        The task is added to the playbook of the configurator.
        Args:
            rule_list: SNAT rules to be set up in the VYOS instance relative to this configurator
        """
        lines = []

        for rule in rule_list:
            lines.append(
                "set nat source rule {} outbound-interface {}".format(rule.rule_number, rule.outbound_interface))
            lines.append(
                "set nat source rule {} source address {}".format(rule.rule_number, rule.source_address))
            lines.append(
                "set nat source rule {} translation address {}".format(rule.rule_number, rule.virtual_ip))

        self.add_vyos_config_task('Configure SNAT rules', 'vyos.vyos.vyos_config', lines)

    def setup_firewall(self, rule_list: List[VyOSFirewallRule]):

        lines = []

        for rule in rule_list:

            if rule.interface_group_name is not None and rule.interface is not None:
                lines.append(f"set firewall group interface-group {rule.interface_group_name} interface {rule.interface}")

            if rule.port_group_name is not None and rule.port_number is not None:
                lines.append(f"set firewall group port-group {rule.port_group_name} port {rule.port_number}")

            if rule.address_group_name is not None and rule.address is not None:
                lines.append(f"set firewall group address-group {rule.address_group_name} address {rule.address}")

            if rule.network_group_name is not None and rule.network is not None:
                lines.append(f"set firewall group network-group {rule.network_group_name} network {rule.network}")


        self.add_vyos_config_task('Configure Firewall rules', 'vyos.vyos.vyos_config', lines)

    def setup_firewall_rules(self, rule_list: List[VyOSFirewallRuleSecond]):

        lines = []

        for rule in rule_list:
            lines.append(f"set firewall name {rule.firewallname} default-action {rule.defaultaction}")
            lines.append(f"set firewall all-ping {rule.en_ping}")
            lines.append(f"set firewall name {rule.firewallname} rule {rule.rule_number} action {rule.action}")
            lines.append(f"set firewall name {rule.firewallname} rule {rule.rule_number} protocol  {rule.protocol}")

            if rule.port is not None:
                lines.append(f"set firewall name {rule.firewallname} rule {rule.rule_number} {rule.var} port {rule.port}")

            if rule.dest_address is not None:
                lines.append(
                    f"set firewall name {rule.firewallname} rule {rule.rule_number} {rule.var} address {rule.dest_address}")

            if rule.port_group_name is not None:
                lines.append(f"set firewall name {rule.firewallname} rule {rule.rule_number} {rule.var} group port-group {rule.port_group_name}")

            if rule.address_group_name is not None:
                lines.append(f"set firewall name {rule.firewallname} rule {rule.rule_number} {rule.var} group address-group {rule.address_group_name}")

            if rule.network_group_name is not None:
                lines.append(f"set firewall name {rule.firewallname} rule {rule.rule_number} {rule.var} group network-group {rule.network_group_name}")

            if rule.interface is not None and rule.variable is not None:
                lines.append(f"set firewall interface {rule.interface} {rule.variable} name {rule.firewallname}")

            #if rule.interface_group_name is not None and rule.variable is not None:
            #    lines.append(f"set firewall interface {rule.interface} {rule.variable} name {rule.firewallname}")

        self.add_vyos_config_task('Configure Firewall rules', 'vyos.vyos.vyos_config', lines)


    def setup_dnat_rules(self, rule_list: List[VyOSDestNATRule]):
        """
        Create instructions for ansible to set up DNAT rules. Instructions are written in self.playbook
        @param rule_list: DNAT rules to set up in the VYOS instance
        """
        lines = []

        for rule in rule_list:
            lines.append(
                "set nat destination rule {} inbound-interface {}".format(rule.rule_number, rule.inbound_interface))
            lines.append(
                "set nat destination rule {} destination address {}".format(rule.rule_number, rule.virtual_ip))
            lines.append(
                "set nat destination rule {} translation address {}".format(rule.rule_number, rule.real_destination_ip))
            lines.append(
                "set nat destination rule {} description '{}'".format(rule.rule_number, rule.description))

        self.add_vyos_config_task('Configure SNAT rules', 'vyos.vyos.vyos_config', lines)

    def delete_nat_rule(self, snat_rule_list: List[VyOSSourceNATRule], dnat_rule_list: List[VyOSDestNATRule]):
        """
        Create instructions for ansible to delete NAT rules. Instructions are written in self.playbook
        @param snat_rule_list: SNAT rules to delete
        @param dnat_rule_list: DNAT rules to delete
        """
        lines = []

        for snat_rule in snat_rule_list:
            lines.append(
                "delete nat source rule {} ".format(snat_rule.rule_number, snat_rule.outbound_interface))
        for dnat_rule in dnat_rule_list:
            lines.append(
                "delete nat destination rule {} ".format(dnat_rule.rule_number, dnat_rule.inbound_interface))

        self.add_vyos_config_task('Deleting NAT rules', 'vyos.vyos.vyos_config', lines)

    def add_vyos_config_task(self, name: str, module: str, lines: List[str]):
        """
        Add the instruction task lines to the playbook, using the desired module (for example vyos.vyos.vyos_config).
        If the playbook is not present it is reset.
        If others tasks are present, the task is appended.

        @param name the name of the task to be appended
        @param module the ansible module to be used
        @param lines the instruction lines of the task
        """
        if not hasattr(self, 'playbook'):
            self.resetPlaybook()
        if not self.playbook['tasks']:
            self.playbook['tasks'] = []
        self.playbook['tasks'].append({'name': name, module: {'lines': lines, 'save': 'yes'}})

    def add_vyos_info_task(self):
        if not self.playbook['tasks']:
            self.playbook['tasks'] = []
        self.playbook['tasks'].append(
            {'name': 'Getting vyos info L3', 'vyos.vyos.vyos_l3_interfaces': {'state': 'gathered'}})

    def change_password_user(self, username: str, password: str):
        if not self.playbook['tasks']:
            self.playbook['tasks'] = []
        self.playbook['tasks'].append(
            {'name': 'Getting vyos info L3', 'vyos.vyos.vyos_user': {'name': username, 'configured_password': password,
                                                                     'update_password': 'always', 'state': 'present'}})

    # Setup ssh user and password
    def add_vyos_config_vars(self, username: str, password: str):
        """
        Add username and password as vars to the playbook. Otherwise, execution fails due to required authentication
        Args:
            username: The vyos username
            password: The vyos password
        """
        self.add_playbook_vars({'ansible_user': username,'ansible_ssh_pass': password,'ansible_password': password})

    def dump(self):
        logger.info("Dumping")
        # The last random part of file name is needed in case 2 or more configuration need to be applied at the same
        # time, otherwise the name of the file will be the same and overwritten.
        self.dumpAnsibleFile(10, '{}_ansible_vyos_{}_{}'.format(self.nsd_id, self.nsd['member-vnfd-id'],
                                                                secrets.token_hex(nbytes=3)))
        return super(Configurator_VyOS, self).dump()

    def destroy(self):
        logger.info("Destroying")
