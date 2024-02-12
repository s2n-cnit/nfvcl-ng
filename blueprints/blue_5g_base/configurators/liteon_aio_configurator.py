from configurators.flex_configurator import Configurator_Flex
from utils import persistency
from utils.log import create_logger
from nfvo.osm_nbi_util import get_osm_nbi_utils

nbiUtil = get_osm_nbi_utils()
db = persistency.DB()
logger = create_logger('Configurator_LiteON_AIO')


class Configurator_LiteON_AIO(Configurator_Flex):
    def __init__(self, nsd_id: str, m_id: int, blue_id: str, args: dict, pdu: dict) -> None:
        if pdu is None or "config" not in pdu:
            raise ValueError("not a valid pdu - pdu = {}".format(pdu))
        self.type = "liteonaio"
        super(Configurator_LiteON_AIO, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Configurator_LiteON_AIO allocated")
        self.day2_conf_file_name = f"liteon_aio_tac_{args['tac']}_plmn_{args['plmn']}_blue_{blue_id}.conf"

        self.conf = pdu['config']  # we start with the config data saved in the db

        self.conf['mcc'] = args['plmn'][:3]
        self.conf['mnc'] = args['plmn'][3:]

        self.conf['gnbid'] = args['tac']
        self.conf['tac'] = args['tac']
        self.conf['nci'] = args['tac']

        self.conf['pci'] = 1  # TODO

        self.conf['sst'] = args['sst']
        self.conf['sd'] = args['sd']

        self.conf['amf_ip'] = args['amf_ip']
        self.conf['upf_ip'] = args['upf_ip']

        self.addPlaybook('blueprints/blue_5g_base/config_scripts/liteon_playbook.yaml', vars_=self.conf)

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_liteon_aio_nb_' + str(self.nsd_id) + '_' + str(self.nsd['member-vnfd-id']))
        return super(Configurator_LiteON_AIO, self).dump()

    def get_logpath(self):
        return [self.conf['log_filename']]

    def destroy(self):
        logger.info("Destroying")
