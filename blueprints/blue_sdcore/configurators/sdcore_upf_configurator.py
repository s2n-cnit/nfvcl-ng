import requests
from pydantic import Field

from configurators.flex_configurator import Configurator_Flex
from models.base_model import NFVCLBaseModel
from utils import persistency
from utils.util import *

db = persistency.DB()
logger = create_logger('ConfiguratorSDCoreUpf')


class ConfiguratorSDCoreUPFVars(NFVCLBaseModel):
    upf_data_cidr: str = Field()
    upf_internet_iface: str = Field()
    upf_ue_ip_pool: str = Field()
    upf_dnn: str = Field()


class ConfiguratorSDCoreUpf(Configurator_Flex):
    def __init__(self, nsd_id: str, m_id: int, blue_id: str, args: ConfiguratorSDCoreUPFVars) -> None:
        self.type = "sdcore_upf"
        super(ConfiguratorSDCoreUpf, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Configurator_SDCore allocated")

        self.addPlaybook("blueprints/blue_sdcore/config_scripts/playbook_upf_init.yaml", {})

        self.addJinjaTemplateFile({
            'template': 'blueprints/blue_sdcore/config_scripts/upf.json.jinja2',
            'path': '/root/upf/conf',
            'transfer_name': f"{blue_id}_upf.json",
            'name': "upf.json"
        }, {
            "upf_ue_ip_pool": args.upf_ue_ip_pool,
            "upf_dnn": args.upf_dnn
        }, ansible_template_resolver=True)

        self.addJinjaTemplateFile({
            'template': 'blueprints/blue_sdcore/config_scripts/run_upf.env.jinja2',
            'path': '/root/upf',
            'transfer_name': f"{blue_id}_run_upf.env",
            'name': "run_upf.env"
        }, {
            "upf_data_cidr": args.upf_data_cidr,
            "upf_internet_iface": args.upf_internet_iface,
            "upf_ue_ip_pool": args.upf_ue_ip_pool
        })

        self.appendPbTasks("blueprints/blue_sdcore/config_scripts/playbook_upf_start.yaml", jinja=False)

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_sdcore_upf_' + str(self.nsd_id) + '_' + str(self.nsd['member-vnfd-id']))
        return super(ConfiguratorSDCoreUpf, self).dump()

    def get_logpath(self):
        return None

    def destroy(self):
        logger.info("Destroying")
