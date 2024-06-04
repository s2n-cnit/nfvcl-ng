from logging import Logger

from nfvcl.configurators.flex_configurator import Configurator_Flex

# create logger
from nfvcl.utils.log import create_logger
logger: Logger = create_logger('Configurator_Amari_gNb')


class Configurator_AmariGNB(Configurator_Flex):
    def __init__(self, nsd_id: str, m_id: int, blue_id: str, args: dict, pdu: dict) -> None:
        if pdu is None or "config" not in pdu:
            raise ValueError("not a valid pdu - pdu = {}".format(pdu))
        self.type = "amarignb"
        super(Configurator_AmariGNB, self).__init__(nsd_id, m_id, blue_id)
        logger.info("{} Configurator_AMARIGNB allocated [nsd: {} vnf_id {}".format(blue_id, nsd_id, m_id))
        self.day2_conf_file_name = 'amari_gnb_tac_' + str(args['tac']) + '_plmn_' + str(args['plmn']) + "_blue_" + blue_id \
                                   + '.conf'

        # self.db = persistency.db()
        self.conf = pdu['config']  # we start with the config data saved in the db
        if 'nb_config' in args:
            self.conf.update(args['nb_config'])

        if 'tunnel' in args:
            self.addShellCmds({'template': 'config_templates/del_vxlans.shell'}, [])

            vxlan_dict = [
                {'placeholder': '__VNI__', 'value': str(args['tunnel']['vni'])},
                {'placeholder': '__REMOTEIP__', 'value': args['tunnel']['remote_ip'].split('/')[0]},
                {'placeholder': '__LOCALIP__', 'value': args['tunnel']['local_ip'].split('/')[0]},
                {'placeholder': '__OVERLAYIP__', 'value': args['gtp_ip'].split('/')[0]},
                {'placeholder': '__OVERLAYIPMASK__', 'value': '24'}
            ]
            self.addShellCmds({'template': 'config_templates/vxlan.shell'}, vxlan_dict)

        self.conf['amf_ip'] = args['amf_ip'] if 'amf_ip' in args else args['mme_ip']
        self.conf['gtp_ip'] = args['gtp_ip']

        plmn_obj = {
            'tac': int(args['tac']),
            'plmn': args['plmn'],
            'reserved': False
        }
        if 'nssai' in args:
            plmn_obj['nssai'] = args['nssai']
        # example: plmn_list = [{
        #   tac: 100,
        #   plmn: "00101",
        #   reserved: false,
        #   nssai: [{sst: 1, }, {sst: 2}, {sst: 3, sd: 50}]
        # }]

        self.conf['plmn_list'] = [plmn_obj]

        '''
        configvar.tdd_config = 2 %}
        configvar.n_antenna_ul = 4 %}
        configvar.n_antenna_ul = 2 %}
        configvar.bandwidth = 20 %}
        configvar.use_srs = 0 %}
        configvar.logfile = "/tmp/gnb0.log" %}
        configvar.amf_addr = "127.0.1.100" %}
        configvar.gtp_addr = "127.0.0.1" %}
        configvar.gnb_id_bits = 28 %}
        configvar.gnb_id = 12345 %}
        configvar.n_id_cell = 500 %}
        plmn_list = [{tac: 100, plmn: "00101", reserved: false, nssai: [{sst: 1, }, {sst: 2}, {sst: 3, sd: 50}]}]
        '''

        self.addJinjaTemplateFile(
            {'template': 'blueprints/blue_5g_base/config_scripts/amariGNb.jinja2',
             'path': '/root/enb/config/',
             'transfer_name': self.day2_conf_file_name,
             'name': 'enb.cfg'
             }, self.conf)

        # restart the Amarisoft services
        self.addShellCmds({'template': 'config_templates/amari_enb_init.shell'}, [])

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_amarignb_' + str(self.nsd_id) + '_' + str(self.nsd['member-vnfd-id']))
        return super(Configurator_AmariGNB, self).dump()

    def get_logpath(self):
        return [self.conf['log_filename']]

    def destroy(self):
        logger.info("Destroying")
