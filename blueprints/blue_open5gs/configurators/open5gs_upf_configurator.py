from configurators.flex_configurator import Configurator_Flex
from utils import persistency
from utils.util import *

db = persistency.db()
logger = create_logger('Configurator_Open5GS_UPF')


class Configurator_Open5GS_UPF(Configurator_Flex):
    def __init__(self, nsd_id: str, m_id: int, blue_id: str, args: dict) -> None:

        self.type = "open5gs_upf"
        super(Configurator_Open5GS_UPF, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Configurator_Open5GS_UPF allocated")
        self.day2_conf_file_name = 'open5gs_upf_tac_{}_plmn_{}_blue_{}.conf'\
            .format(args['tac'], str(args['plmn']), blue_id)

        self.conf = {}

        conf_file = 'upf.yaml'
        self.addJinjaTemplateFile(
            {'template': 'config_templates/upf_open5gs.jinja2',
             'path': '/etc/open5gs/',
             'transfer_name': self.day2_conf_file_name,
             'name': conf_file
             }, self.conf)

        # self.addShellCmds({'template': 'config_templates/ueransim_nb_init.shell'}, [])
        ansible_vars = {'conf_file': conf_file}
        self.appendJinjaPbTasks('config_templates/playbook_upf_open5gs.yaml', vars_=ansible_vars)

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_open5gs_upf_' + str(self.nsd_id) + '_' + str(self.nsd['member-vnfd-id']))
        return super(Configurator_Open5GS_UPF, self).dump()

    def get_logpath(self):
        return [self.conf['log_filename']]

    def destroy(self):
        logger.info("Destroying")
