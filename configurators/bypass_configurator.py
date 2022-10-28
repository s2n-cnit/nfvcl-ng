import logging
from configurators.flex_configurator import Configurator_Flex
#import paramiko

# create logger
logger = logging.getLogger('Configurator_Bypass')
logger.setLevel(logging.INFO)
# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# add formatter to ch
ch.setFormatter(formatter)
# add ch to logger
logger.addHandler(ch)


class Configurator_Bypass(Configurator_Flex):
    def __init__(self, nsd_id, m_id, blue_id, vxlan_enb, vxlan_epc, plmn, tac, dc_ip):
        self.type = "bypass"
        self.conf = {'plmn': plmn}
        self.vxlan_epc = vxlan_epc
        self.vxlan_enb = vxlan_enb
        self.tac = tac
        self.nets = []
        self.dc_ip = dc_ip
        ipg = str(dc_ip).split('.')
        ip_gw = str(ipg[0]) + '.' + str(ipg[1]) + '.' + str(ipg[2]) + '.1'
        super(Configurator_Bypass, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Configurator_Bypass allocated")
        placeholder_dict = [
            {'placeholder': '__S1ENB_VNI__', 'value': str(vxlan_enb['vni'])},
            {'placeholder': '__S1ENB_BYPIP__', 'value': str(vxlan_enb['local_ip']).split('/')[0]},
            {'placeholder': '__S1ENB_ENBIP__', 'value': str(vxlan_enb['remote_ip']).split('/')[0]},
            {'placeholder': '__S1MME_VNI__', 'value': str(vxlan_epc['vni'])},
            {'placeholder': '__S1MME_BYPIP__', 'value': str(vxlan_epc['local_ip']).split('/')[0]},
            {'placeholder': '__S1MME_MMEIP__', 'value': str(vxlan_epc['remote_ip']).split('/')[0]},
            {'placeholder': '__DC_IP__', 'value': str(self.dc_ip)},
            {'placeholder': '__DC_NET__', 'value': "10.0.0.0/16"},
            {'placeholder': '__DC_GW__', 'value': ip_gw }
        ]
        self.addShellCmds(
            {'template': 'config_templates/bypass_init.shell'}, placeholder_dict)
    def add_app(self, net_):
        # here we need to generate an ansible playbook with a http module command
        url = 'http://' + self.mng_ip + ':8080/api/register_dc_network'
        message = { 'network': { 'address': net_['address'], 'mask': net_['mask'] } }
        self.addRestCmd(url, message, 'POST', 204)
        #self.nets.append(net_)
        return

    def del_app(self, net_):
        # here we need to generate an ansible playbook with a http module command
        '''
        for n in self.nets[:]:
                if n['network'] == net_['network'] and n['netmask'] == net_['netmask']:
                        payload = { 'network': { 'address': net_['address'], 'netmask': net_['netmask'] } }
                        url = 'http://' + self.mng_ip + '/api/register_dc_network'
                        response = requests.post(url, json=payload)
                        if response.status_code == requests.codes.ok:
                                print("Bypass networks updated")
                        else:
                                print("Bypass network updating error")

                        self.nets.remove(n)
                        return True
        '''
        url = 'http://' + self.mng_ip + '/api/register_dc_network'
        message = { 'network': { 'address': net_['address'], 'mask': net_['mask'] } }
        method = 'DELETE'
        self.addRestCmd(url, message, method, 204)

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_bypass_'+str(self.nsd_id) +
                             '_'+str(self.nsd['member-vnfd-id']))

        return super(Configurator_Bypass, self).dump()

    def dump_nets(self):
        return self.nets
