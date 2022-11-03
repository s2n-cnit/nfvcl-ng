from configurators.flex_configurator import Configurator_Flex
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString
import json
import re
from utils import persistency
import logging

# create logger
logger = logging.getLogger('Configurator_AmarieNb')
logger.setLevel(logging.INFO)
# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# add formatter to ch
ch.setFormatter(formatter)
# add ch to logger
logger.addHandler(ch)


class Configurator_AmariENB(Configurator_Flex):
    def __init__(self, nsd_id, m_id, blue_id, args):
        # global OSSdb

        self.type = "amarienb"
        super(Configurator_AmariENB, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Configurator_AMARIENB allocated")
        self.db = persistency.DB()

        self.mgt_ip = args["mgt_ip"]
        # self.nsd_id = nsd_id
        # self.nsd = {'member-vnfd-id': m_id}
        # db = persistency.db()
        yaml = YAML(typ="rt")
        yaml.default_flow_style = True
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)

        # choose the template according to the tac
        self.addTemplateFile(
            {'template': 'config_templates/amari_enb_tac' + str(args['tac']) + '.cfg',
             'path': '/root/enb/config',
             'transfer_name': 'amari_enb_plmn_' + str(args['plmn']) + '_tac_' + str(args['tac']) + '.cfg',
             'name': 'enb.cfg'}, [])

        with open('day2_files/amari_enb_plmn_' + str(args['plmn']) + '_tac_' + str(args['tac']) + '.cfg') as f:
            self.conf = yaml.load(f)
            for c in self.conf["cell_list"]:
                c["plmn_list"].append(DoubleQuotedScalarString(args["plmn"]))
            if "nb_cell_list" in self.conf:
                for c in self.conf["nb_cell_list"]:
                    c["plmn_list"].append({'plmn': DoubleQuotedScalarString(args["plmn"]), 'reserved': False})
            if "mme_addr" in self.conf:
                self.conf["mme_addr"] = DoubleQuotedScalarString(args['mme_ip'])
            if "mme_list" in self.conf:
                self.conf["mme_list"].append({"mme_addr": DoubleQuotedScalarString(args['mme_ip'])})
            self.conf["gtp_addr"] = DoubleQuotedScalarString(args['gtp_ip'])
            if "license_server" in self.conf:
                self.conf["license_server"]["server_addr"] = DoubleQuotedScalarString(self.acquire_license())

        # with open('day2_files/amari_enb_plmn_'+ str(args['plmn']) +'_tac_'+ str(args['tac']) + '.cfg', 'w') as f:
        #    yaml.dump(self.conf, f)

        # this dumping produces a multiline file with the right quotes
        with open('day2_files/amari_enb_plmn_' + str(args['plmn']) + '_tac_' + str(args['tac']) + '.cfg', 'w') as f:
            f.write(re.sub(r'"(.*?)"(?=:)', r'\1', json.dumps(self.conf, indent=2, separators=(',', ': '))))

        self.addShellCmds(
            {'template': 'config_templates/del_vxlans.shell'}, [])

        # configure the optional vxlan tunnels
        if 'tunnel' in args:
            vxlan_dict = [
                {'placeholder': '__VNI__', 'value': str(args['tunnel']['vni'])},
                {'placeholder': '__REMOTEIP__', 'value': args['tunnel']['remote_ip'].split('/')[0]},
                {'placeholder': '__LOCALIP__', 'value': args['tunnel']['local_ip'].split('/')[0]},
                {'placeholder': '__OVERLAYIP__', 'value': args['gtp_ip'].split('/')[0]},
                {'placeholder': '__OVERLAYIPMASK__', 'value': '24'}
            ]
            self.addShellCmds({'template': 'config_templates/vxlan.shell'}, vxlan_dict)

        # run the Amarisoft eNB software
        placeholder_dict = []
        self.addShellCmds(
            {'template': 'config_templates/amari_enb_init.shell'}, placeholder_dict)
        # FIXME: the s1ap is only in the CNIT testbed
        if str(args['tac']) == "2":
            logger.info("TAC with s1AP!!!!!!!!")
            placeholder_dict = [
                {'placeholder': '__ENB_VXLAN_INTERFACE__', 'value': "vxlan" + str(args['tunnel']['vni'])},
                {'placeholder': '__BYPASS_MGT_IP__', 'value': str(args['byp_mgt_ip'])}
            ]
            self.addShellCmds(
                {'template': 'config_templates/amari_enb_s1ap.shell'}, placeholder_dict)
        else:
            logger.info("TAC without s1AP!!!!!!!!        ---- TAC=" + str(args['tac']))
        logger.info("Allocation end")

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_amarienb_' + str(self.nsd_id) + '_' + str(self.nsd['member-vnfd-id']))
        return super(Configurator_AmariENB, self).dump()

    def get_logpath(self):
        return [self.conf['log_filename']]

    def acquire_license(self):
        logger.info("Acquiring license")
        license_servers = self.db.find_DB("license", {"license.type": "amarienb", "license.version": "2019-02-05"})
        license_ip = ""
        for server in license_servers:
            if server["license"]["number"] > len(server["license"]["consumer"]):
                license_ip = server["license"]["ip"]
                server["license"]["consumer"].append(self.mgt_ip)
                # .update_one(filter, {"$set": data})
                res = self.db.update_DB("license", server, {'license.ip': server['license']['ip'],
                                                            'license.type': server['license']['type']})
                print(res)
                break

        if license_ip is "":
            raise ValueError("no Amarisoft License Servers available")

        return license_ip

    def release_license(self):
        logger.info("Releasing license")
        license_servers = self.db.find_DB("license", {"license.type": "amarienb",
                                                      "license.ip": self.conf["license_server"]["server_addr"]})
        for server in license_servers:
            if self.mgt_ip in server["license"]["consumer"]:
                server["license"]["consumer"].remove(self.mgt_ip)
                self.db.update_DB("license", server,
                                  {'license.ip': server['license']['ip'], 'license.type': server['license']['type']})
                break

    def destroy(self):
        logger.info("Destroying")
        self.release_license()

        # super(Configurator_AmariENB, self).destroy()
