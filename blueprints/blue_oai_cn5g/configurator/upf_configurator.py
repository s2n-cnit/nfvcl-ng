from configurators.flex_configurator import Configurator_Flex
from utils.log import create_logger

logger = create_logger('Configurator_OAI_UPF')


class Configurator_OAI_UPF(Configurator_Flex):
    def __init__(self, nsd_id: str, m_id: int, blue_id: str, args: dict):
        super(Configurator_OAI_UPF, self).__init__(nsd_id, m_id, blue_id)

        # self.addPlaybook('blueprints/blue_oai_cn5g/configurator_scripts/upfDirectoryCreation.yaml', vars_={})

        self.conf = {
            "ip": args["ip"],
            "interface": args["interface"]
        }

        self.addJinjaTemplateFile({
            'template': 'blueprints/blue_oai_cn5g/configurator_scripts/compose.jinja2',
            'path': '/root/upfConfig',
            'transfer_name': f"{blue_id}_compose.yaml",
            'name': "compose.yaml"
        }, self.conf)

        self.appendPbTasks('blueprints/blue_oai_cn5g/configurator_scripts/compose.yaml')

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_oai_upf_' + str(self.nsd_id) + '_' + str(self.nsd['member-vnfd-id']))
        return super(Configurator_OAI_UPF, self).dump()

    def get_logpath(self):
        return None

    def destroy(self):
        logger.info("Destroying")
