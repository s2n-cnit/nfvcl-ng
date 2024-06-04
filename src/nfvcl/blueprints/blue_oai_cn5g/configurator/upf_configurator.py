from nfvcl.configurators.flex_configurator import Configurator_Flex
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.utils.log import create_logger
from pydantic import Field

logger = create_logger('Configurator_OAI_UPF')


class ConfiguratorOAIUPFVars(NFVCLBaseModel):
    upf_id: int = Field()
    nrf_ipv4_address: str = Field()
    upf_conf: str = Field()


class Configurator_OAI_UPF(Configurator_Flex):
    def __init__(self, nsd_id: str, m_id: int, blue_id: str, args: ConfiguratorOAIUPFVars):
        super(Configurator_OAI_UPF, self).__init__(nsd_id, m_id, blue_id)

        self.conf = {
            "upf_id": args.upf_id,
            "nrf_ipv4_address": args.nrf_ipv4_address,
            "upf_conf": args.upf_conf
        }

        self.addJinjaTemplateFile({
            'template': 'blueprints/blue_oai_cn5g/configurator_scripts/compose.jinja2',
            'path': '/root/upfConfig',
            'transfer_name': f"{blue_id}_{args.upf_id}_compose.yaml",
            'name': "compose.yaml"
        }, self.conf)

        self.addJinjaTemplateFile({
            'template': 'blueprints/blue_oai_cn5g/configurator_scripts/upf_conf.jinja2',
            'path': '/root/upfConfig/conf',
            'transfer_name': f"{blue_id}_{args.upf_id}_basic_nrf_config.yaml",
            'name': "basic_nrf_config.yaml"
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
