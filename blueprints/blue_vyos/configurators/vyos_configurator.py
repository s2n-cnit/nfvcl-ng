from typing import List
from ipaddress import IPv4Network
from configurators.flex_configurator import Configurator_Flex
from ..models import VyOSRouterNetworkEndpoints, VyOSSourceNATRule, VyOSDestNATRule
import secrets
import logging

# create logger
logger = logging.getLogger('Configurator_VyOS')
logger.setLevel(logging.INFO)
# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# add formatter to ch
ch.setFormatter(formatter)
# add ch to logger
logger.addHandler(ch)

class Configurator_VyOS(Configurator_Flex):
    router_area_id: int
    network_endpoints: VyOSRouterNetworkEndpoints

    def __init__(self, area_id: int, nsd_name: str, m_id: int, blue_id: str,
                 network_endpoints: VyOSRouterNetworkEndpoints = None, username: str = 'vyos', password: str = 'vyos'):
        # NOTE: args is the tac obj within blue.conf
        self.network_endpoints = network_endpoints
        self.router_area_id = area_id
        self.type = "VyOS"
        super(Configurator_VyOS, self).__init__(nsd_name, m_id, blue_id)

        logger.info("Configurator_VyOs created")

    def initial_configuration(self):
        """
        Perform initial configuration for VyOS router, this includes:
        -Playbook loading
        -setup account and password for ansible (in order to configure vyos)
        -add configuration task to playbook for data interfaces
        -add configuration task to playbook for loopback in
        """
        # Do not set as second arg an empty list, or it will override the playbook vars
        self.addPlaybook('blueprints/blue_vyos/config_scripts/playbook_vyos.yaml')
        self.add_vyos_config_vars(username='vyos', password='vyos')

        self.setup_data_interfaces()
        self.setup_loopback_ip()
        self.add_vyos_info_task()

    def setup_loopback_ip(self):
        lines = []
        loopback_ipaddr = "10.200." + str(self.router_area_id) + ".1/32"
        lines.append("set interfaces loopback lo address {}".format(loopback_ipaddr))
        self.add_vyos_config_task('Configuring loopback', 'vyos.vyos.vyos_config', lines)

    def setup_data_interfaces(self):
        """
        Once the configurator is build. It is possible to create instructions to set up data interfaces for ansible.
        Instructions are written in self.playbook.
        """
        lines = []

        interface_index = 1  # STARTING From 1 because management interface is always present and called eth0
        # This code works because vyos create sequentials interfaces starting from eth0, eth1, eth2, ..., ethN
        for network in self.network_endpoints.data_nets:
            # Getting prefix lenght
            prefix_length = IPv4Network(network.network).prefixlen

            interface_address = network.ip_addr
            # NOTE: the ip address is got by get IP address, but OSM is not reporting netmask! setting /24 as default
            if interface_address is None:
                lines.append("set interfaces ethernet eth{} address dhcp".format(interface_index))
            else:
                lines.append("set interfaces ethernet eth{} address {}/{}".format(interface_index, interface_address,
                                                                                  prefix_length))
            lines.append("set interfaces ethernet eth{} description \'{}\'".format(interface_index, self.blue_id))
            lines.append("set interfaces ethernet eth{} duplex auto".format(interface_index))
            lines.append("set interfaces ethernet eth{} speed auto".format(interface_index))
            #MAX supported MTU is 1450
            lines.append("set interfaces ethernet eth{} mtu 1450".format(interface_index))
            interface_index = interface_index + 1
        self.add_vyos_config_task('Configure DATA Interfaces', 'vyos.vyos.vyos_config', lines)

    def setup_snat_rules(self, rule_list: List[VyOSSourceNATRule]):
        """
        Create instructions for ansible to set up SNAT rules. Instructions are written in self.playbook
        @param rule_list: SNAT rules to set up in the VYOS instance
        """
        lines = []

        for rule in rule_list:
            lines.append(
                "set nat source rule {} outbound-interface {}".format(rule.rule_number, rule.outbound_interface))
            lines.append(
                "set nat source rule {} source address {}".format(rule.rule_number, rule.source_address))
            lines.append(
                "set nat source rule {} translation address {}".format(rule.rule_number,rule.virtual_ip))

        self.addPlaybook('blueprints/blue_vyos/config_scripts/playbook_empty_vyos.yaml')

        self.add_vyos_config_task('Configure SNAT rules', 'vyos.vyos.vyos_config', lines)

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

        self.addPlaybook('blueprints/blue_vyos/config_scripts/playbook_empty_vyos.yaml')

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

        self.addPlaybook('blueprints/blue_vyos/config_scripts/playbook_empty_vyos.yaml')

        self.add_vyos_config_task('Deleting NAT rules', 'vyos.vyos.vyos_config', lines)

    def add_vyos_config_task(self, name:str, module:str, lines:List[str]):
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
            self.playbook['tasks']=[]
        self.playbook['tasks'].append({'name': name, module: {'lines': lines, 'save': 'yes'}})

    def add_vyos_info_task(self):
        if not self.playbook['tasks']:
            self.playbook['tasks'] = []
        self.playbook['tasks'].append(
            {'name': 'Getting vyos info L3', 'vyos.vyos.vyos_l3_interfaces': {'state': 'gathered'}})

    # Setup ssh user and password
    def add_vyos_config_vars(self, username: str, password: str):
        if not self.playbook['vars']:
            self.playbook['vars'] = []
        self.playbook['vars'].append({'ansible_user': username})
        self.playbook['vars'].append({'ansible_ssh_pass': password})

    def dump(self):
        logger.info("Dumping")
        # The last random part of file name is needed in case 2 or more configuration need to be applied at the same
        # time, otherwise the name of the file will be the same and overwritten.
        self.dumpAnsibleFile(10, 'ansible_vyos_' + str(self.nsd_id) +
                             '_' + str(self.nsd['member-vnfd-id']) + secrets.token_hex(nbytes=3))
        return super(Configurator_VyOS, self).dump()

    def enable_elk(self, args):
        self.addPlaybook('config_templates/playbook_vyos.yaml', vars_=[])
        lines = []
        for u in args["logstash.url"]:
            lines.append("set system syslog host " + str(u) + " facility all level all")
        self.add_vyos_config_task('configure elk', 'vyos.vyos.vyos_config', lines)
        return self.dump()

    def custom_prometheus_exporter(self):
        # self.addPackage('screen')
        pass

    def destroy(self):
        logger.info("Destroying")
        # TODO remove prometheus jobs
