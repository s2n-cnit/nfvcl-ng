from configurators.flex_configurator import Configurator_Flex
from utils import persistency
from utils.util import *

db = persistency.db()
logger = create_logger('Configurator_UeRanSimNB')


class Configurator_UeRanSimNB(Configurator_Flex):
    def __init__(self, nsd_id: str, m_id: int, blue_id: str, args: dict) -> None:

        self.type = "euransim"
        super(Configurator_UeRanSimNB, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Configurator_UeRanSimNB allocated")
        self.day2_conf_file_name = 'ueransim_nb_tac_{}_plmn_{}_blue_{}.conf'\
            .format(args['tac'], str(args['plmn']), blue_id)

        persistent_data = db.findone_DB('pdu', {'tac': str( args['tac'] )})
        self.conf = persistent_data['config']  # we start with the config data saved in the db
        if 'nb_config' in args:
            #from here we should retrieve cell id and radio addr
            self.conf.update(args['nb_config'])

        self.conf['plmn'] = args['plmn']
        self.conf['tac'] = args['tac']
        self.conf['amf_ip'] = args['amf_ip']
        self.conf['gtp_addr'] = args['gtp_ip']
        self.conf['ngap_addr'] = args['gtp_ip']
        if 'amf_port' not in args:
            self.conf['amf_port'] = 38412


        if 'nssai' in args:
            if isinstance(self.conf['nssai'], list):
                self.conf['nssai'] = args['nssai']
            else:
                self.conf['nssai'] = [args['nssai']]
        else:
            self.conf['nssai'] = [{'sst': 1, 'sd': 1}]

        conf_file = 'nb.cfg'
        self.addJinjaTemplateFile(
            {'template': 'config_templates/nb_ueransim.jinja2',
             'path': '/root/',
             'transfer_name': self.day2_conf_file_name,
             'name': conf_file
             }, self.conf)

        # self.addShellCmds({'template': 'config_templates/ueransim_nb_init.shell'}, [])
        ansible_vars = {'conf_file': conf_file}
        self.appendJinjaPbTasks('config_templates/playbook_nb_ueransim.yaml', vars_=ansible_vars)

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_ueransim_nb_' + str(self.nsd_id) + '_' + str(self.nsd['member-vnfd-id']))
        return super(Configurator_UeRanSimNB, self).dump()

    def get_logpath(self):
        return [self.conf['log_filename']]

    def destroy(self):
        logger.info("Destroying")
