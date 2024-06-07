import requests

from nfvcl.configurators.flex_configurator import Configurator_Flex
from nfvcl.utils import persistency
from nfvcl.utils.util import *

db = persistency.DB()
logger = create_logger('Configurator sdcore')


class Configurator_SDCore(Configurator_Flex):
    def __init__(self, nsd_id: str, m_id: int, blue_id: str, args: dict) -> None:
        self.type = "sdcore"
        #super(Configurator_SDCore, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Configurator_SDCore allocated")
        # self.day2_conf_file_name = 'open5gs_upf_tac_{}_plmn_{}_blue_{}.conf'.format(args['tac'], str(args['plmn']), blue_id)
        #
        # self.conf = {}
        #
        # conf_file = 'upf.yaml'
        # self.addJinjaTemplateFile(
        #     {'template': 'config_templates/upf_open5gs.jinja2',
        #      'path': '/etc/open5gs/',
        #      'transfer_name': self.day2_conf_file_name,
        #      'name': conf_file
        #      }, self.conf)
        #
        # # self.addShellCmds({'template': 'config_templates/ueransim_nb_init.shell'}, [])
        # ansible_vars = {'conf_file': conf_file}
        # self.appendJinjaPbTasks('config_templates/playbook_upf_open5gs.yaml', vars_=ansible_vars)

        aaa = {
          "UeId":"111130100007587",
          "plmnId":"20801",
          "opc":"d4416644f6154936193433dd20a0ace0",
          "key":"465b5ce8b199b49faa5f0a2ee238a6bc",
          "sequenceNumber":"96"
      }


        x = requests.post(f"http://{args['webui_ip']}:5000/api/subscriber/imsi-111130100007587", json=aaa)

        logger.critical(f"#######################: {x.text}")

        # self.addRestCmd(f"http://{args['webui_ip']}:5000/api/subscriber/imsi-111130100007587", aaa, "POST", 201)

    # def dump(self):
    #     logger.info("Dumping")
    #     self.dumpAnsibleFile(10, 'ansible_sdcore_' + str(self.nsd_id) + '_' + str(self.nsd['member-vnfd-id']))
    #     return super(Configurator_SDCore, self).dump()
    #
    # def get_logpath(self):
    #     return None
    #
    # def destroy(self):
    #     logger.info("Destroying")
