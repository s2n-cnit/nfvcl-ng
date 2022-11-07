from configurators.flex_configurator import Configurator_Flex
from utils.util import *

logger = create_logger('ConfiguratorUeRanSim')

class ConfiguratorUeUeRanSim(Configurator_Flex):
    def __init__(self, nsd_id, m_id, blue_id, args):
        self.type = "UE_ueransim"
        super(ConfiguratorUeUeRanSim, self).__init__(nsd_id, m_id, blue_id)
        self.addPlaybook("blueprints/blue_ueransim/config_scripts/playbook_ue_ueransim_init.yaml")
        logger.debug("ConfiguratorUeUeRanSim created.\ngnbSearchList: {}".format(args['vim_gnbs_ips']))
        for sim_index, sim in enumerate(args['sims']):
            jinja_vars = {
                'sim': sim,
                'gnbSearchList': args['vim_gnbs_ips'],
            }
            conf_file = "sim_{}.yaml".format(sim_index)
            self.addJinjaTemplateFile({'template': 'blueprints/blue_ueransim/config_scripts/ue_ueransim.jinja2',
                     'path': '/root/',
                     'transfer_name': "{}_ue-{}_sim-{}.yaml".format(blue_id, args['id'], sim_index),
                     'name': conf_file
                     }, jinja_vars)
            self.appendJinjaPbTasks('blueprints/blue_ueransim/config_scripts/playbook_ue_ueransim.yaml', vars_=
                {'conf_file': conf_file, 'sim_id': sim_index})

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_UE_URS_' + str(self.nsd_id) +
                             '_' + str(self.nsd['member-vnfd-id']))
        return super(ConfiguratorUeUeRanSim, self).dump()

    def get_logpath(self):
        # return [self.conf['log_filename']]
        return []

    def custom_prometheus_exporter(self):
        # self.addPackage('screen')
        pass

    def destroy(self):
        logger.info("Destroying")
        # TODO remove prometheus jobs