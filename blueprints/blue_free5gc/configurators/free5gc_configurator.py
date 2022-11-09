import blueprints.blue_free5gc.blueprint_Free5GC_K8s

from configurators.flex_configurator import Configurator_Flex
from utils.util import *

logger = create_logger('Configurator_Free5GC')

class Configurator_Free5GC(Configurator_Flex):
    def __init__(self, nsd_id: str, m_id: int, blue_id: str, args: dict) -> None:
        # Check the type of the module
        self.nsd_type = nsd_id.split("_")
        if self.nsd_type and self.nsd_type[0].lower() in \
                blueprints.blue_free5gc.blueprint_Free5GC_K8s.Free5GC_K8s.edge_vnfd_type:
            self.nsd_type = self.nsd_type[0].lower()
        else:
            logger.error("nsd type not recognized or not defined")
            return

        self.type = "free5gc_{}".format(self.nsd_type)
        super(Configurator_Free5GC, self).__init__(nsd_id, m_id, blue_id)

        logger.info("Configurator_Free5GC allocated for {}".format(self.nsd_type.upper()))

        if "tac" in args:
            self.day2_conf_file_name = 'free5gc_{}_tac_{}_plmn_{}_blue_{}.conf'\
                .format(self.nsd_type, args['tac'], str(args['plmn']), blue_id)
        else:
            self.day2_conf_file_name = 'free5gc_{}_plmn_{}_blue_{}.conf'\
                .format(self.nsd_type, str(args['plmn']), blue_id)

        self.conf = {}
        if self.nsd_type == "upf":
            upf = next((item for item in args['upf_nodes'] if item['ns_id'] == nsd_id), None)
            if upf == None:
                self.conf["pfcp"] = []
                self.conf["gtpu"] = []
                self.conf["dnn_list"] = []
            else:
                self.conf["pfcp"] = [upf["ip"]]
                self.conf["gtpu"] = [upf["ip"]]
                self.conf["dnn_list"] = upf["dnnList"]
        else:
            raise("ERROR: nsd type is not UPF")

        conf_file = '{}cfg.yaml'.format(self.nsd_type)
        self.addJinjaTemplateFile(
            {'template': 'config_templates/{}_free5gc.jinja2'.format(self.nsd_type),
             'path': '/root/free5gc/config',
             'transfer_name': self.day2_conf_file_name,
             'name': conf_file
             }, self.conf)

        removingDnnList = []
        if "removingDnnList" in args:
            removingDnnList = args["removingDnnList"]

        ansible_vars = {'conf_file': conf_file, 'type': self.nsd_type, 'dnn_list': self.conf["dnn_list"],
                        'removing_dnn_list': removingDnnList}
        if self.nsd_type == "upf":
            self.appendJinjaPbTasks('config_templates/playbook_upf_free5gc.yaml', vars_=ansible_vars)
        else:
            self.appendJinjaPbTasks('config_templates/playbook_free5gc.yaml', vars_=ansible_vars)

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_free5gc_' + self.nsd_type
                             + '_' + str(self.nsd_id) + '_' + str(self.nsd['member-vnfd-id']))
        return super(Configurator_Free5GC, self).dump()

    def get_logpath(self):
        return [self.conf['log_filename']]

    def destroy(self):
        logger.info("Destroying")
