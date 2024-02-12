from configurators.flex_configurator import Configurator_Flex
from models.ueransim.blueprint_ueransim_model import UeransimUe
from utils.log import create_logger
logger = create_logger('ConfiguratorUeRanSim')

class ConfiguratorUeUeRanSimBeta(Configurator_Flex):
    def __init__(self, nsd_id, m_id, blue_id, user_equipment: UeransimUe):
        logger.debug(f"ConfiguratorUeUeRanSim initialized.\ngnbSearchList: {user_equipment.vim_gnbs_ips}")
        super(ConfiguratorUeUeRanSimBeta, self).__init__(nsd_id, m_id, blue_id)
        self.type = "UE_ueransim"
        # Add a playbook to disable auto updates in ubuntu (to avoid startup problems)
        self.addPlaybook("blueprints/blue_ueransim/config_scripts/playbook_ue_ueransim_init.yaml", vars_={})

        # Every UE can have multiple sim (simulations?) [Basically start a new virtual device for each sim]
        # FOR EVERY SIM in UE -> Configure and start an UEransim virtual device
        for sim_index, sim in enumerate(user_equipment.sims):
            # For each sim compile the jinja template for config and for ansible device startup
            jinja_vars = {
                'sim': sim,
                'gnbSearchList': user_equipment.vim_gnbs_ips,
            }
            conf_file = f"sim_{sim_index}.yaml"
            # Compile the configuration
            self.addJinjaTemplateFile({'template': 'blueprints/blue_ueransim/config_scripts/ue_ueransim.jinja2',
                     'path': '/root/',
                     'transfer_name': f"{blue_id}_ue-{user_equipment.id}_sim-{sim_index}.yaml",
                     'name': conf_file
                     }, jinja_vars)
            # Start the virtual device
            self.appendJinjaPbTasks('blueprints/blue_ueransim/config_scripts/playbook_ue_ueransim.yaml', vars_=
                {'conf_file': conf_file, 'sim_id': sim_index})

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_UE_URS_' + str(self.nsd_id) +
                             '_' + str(self.nsd['member-vnfd-id']))
        return super(ConfiguratorUeUeRanSimBeta, self).dump()

    def get_logpath(self):
        # return [self.conf['log_filename']]
        return []

    def custom_prometheus_exporter(self):
        # self.addPackage('screen')
        pass

    def destroy(self):
        logger.info("Destroying")
        # TODO remove prometheus jobs
