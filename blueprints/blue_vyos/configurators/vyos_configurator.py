from configurators.configurator import Configurator_Base
from configurators.flex_configurator import Configurator_Flex
import logging

# create logger
logger = logging.getLogger('Configurator_K8s')
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


class Configurator_VyOs(Configurator_Flex):
    def __init__(self, nsd_id, m_id, blue_id, args):
        # NOTE: args is the tac obj within blue.conf

        self.type = "VyOS"
        super(Configurator_VyOs, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Configurator_VyOs created")
        # self.db = persistency.db()

        ansible_vars = []

        loopback_ipaddr = "10.200." + str(args['id']) + ".1/32"
        self.addPlaybook('config_templates/playbook_vyos.yaml', vars_=ansible_vars)

        lines = []
        for intf in args['interfaces']:
            if 'mgt' in intf:
                if intf['mgt']:
                    # skipping the mgt interface since it is already configured
                    continue
            # NOTE: the ip address is got by get IP address, but OSM is not reporting netmask! setting /24 as default
            lines.append("set interfaces ethernet " + intf['name'] + " address " + intf['ip_address'] + '/24')
            lines.append("set interfaces ethernet " + intf['name'] + " description " + intf['vld'])
            lines.append("set interfaces ethernet " + intf['name'] + " duplex auto")
            lines.append("set interfaces ethernet " + intf['name'] + " speed auto")
        lines.append("set interfaces loopback lo address " + loopback_ipaddr)
        self.addVyOS_config_task('step 1 configure interfaces', lines)

    def addVyOS_config_task(self, name, lines):
        if not hasattr(self, 'playbook'):
            self.resetPlaybook()
        self.playbook['tasks'].append({'name': name, 'vyos.vyos.vyos_config': {'lines': lines}})

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_vyos_' + str(self.nsd_id) +
                             '_' + str(self.nsd['member-vnfd-id']))
        return super(Configurator_VyOs, self).dump()

    def enable_elk(self, args):
        self.addPlaybook('config_templates/playbook_vyos.yaml', vars_=[])
        lines = []
        for u in args["logstash.url"]:
            lines.append("set system syslog host " + str( u ) + " facility all level all")
        self.addVyOS_config_task('configure elk', lines)
        return self.dump()

    def custom_prometheus_exporter(self):
        # self.addPackage('screen')
        pass

    def destroy(self):
        logger.info("Destroying")
        # TODO remove prometheus jobs



class Configurator_MultiVyOs(Configurator_Base):
    def __init__(self, nsd_id, m_id, router_id, local_ip, peers):
        self.nsd_id = nsd_id
        self.nsd = {'member-vnfd-id': m_id}
        self.type = "vyos"
        self.monitoring_tools = []
        self.local_ip = local_ip  # ip address on the wan interface
        self.peers = peers  # [{id:, remote_ip:, net_id: }]
        self.id = router_id

    def dump(self):
        cmds = {}
        cmds['conf'] = [
            "set interfaces ethernet eth1 address dhcp",
            "set interfaces ethernet eth1 description INSIDE",
            "set interfaces ethernet eth1 duplex auto",
            "set interfaces ethernet eth1 speed auto",
            "set interfaces ethernet eth2 address " + str(self.local_ip),
            "set interfaces ethernet eth2 description OUTSIDE",
            "set interfaces ethernet eth2 duplex auto",
            "set interfaces ethernet eth2 speed auto",
            "set interfaces loopback lo address 1.10.1." + str(self.id) + "/32",
            "set policy route-map CONNECT rule 10 action permit",
            "set policy route-map CONNECT rule 10 match interface eth1",
            "set protocols ospf area 0 network 1.10.1.0/24",
            "set protocols ospf parameters router-id 1.10.1." + str(self.id),
            "set protocols ospf redistribute connected route-map CONNECT"
        ]
        if str(self.local_ip).split('.')[0] == "10":
            cmds['conf'].append("set protocols static route 172.16.0.0/24 next-hop 10.254.99.1 distance 1")
        if str(self.local_ip).split('.')[0] == "172":
            cmds['conf'].append("set protocols static route 10.254.99.0/24 next-hop 172.16.0.80 distance 1")
        for p_ in self.peers:
            print("-----------> RouterID: " + str(self.id) + " Peer: " + str(p_['id'])+"\n")
            if int(self.id) < int(p_['id']):
                cmds['conf'].append(
                    "set interfaces tunnel tun" + str(p_['net_id']) + " address 10.1." + str(p_['net_id']) + ".1/30")
            else:
                cmds['conf'].append(
                    "set interfaces tunnel tun" + str(p_['net_id']) + " address 10.1." + str(p_['net_id']) + ".2/30")
            cmds['conf'].append(
                "set protocols ospf area 0 network 10.1." + str(p_['net_id']) + ".0/30")

            cmds['conf'].append("set interfaces tunnel tun" + str(p_['net_id']) + " encapsulation 'ipip'")
            cmds['conf'].append("set interfaces tunnel tun" + str(p_['net_id']) + " local-ip '" + str(self.local_ip).split('/')[0] + "'")
            cmds['conf'].append("set interfaces tunnel tun" + str(p_['net_id']) + " multicast 'disable'")
            cmds['conf'].append("set interfaces tunnel tun" + str(p_['net_id']) + " remote-ip '" + str(p_['remote_ip']).split('/')[0] + "'")

        self.config_content = cmds
        return self.dump_()

    def enable_elk(self, args):
        cmds = {}

        self.monitoring_tools.append("elk")
        cmds['conf'] = []
        for u in args["logstash.url"]:
            cmds['conf'].append("set system syslog host " + str( u ) + " facility all level all")

        self.config_content = cmds

        return self.dump_()
