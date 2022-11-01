from blueprints import BlueprintBase, parse_ansible_output
from . import Configurator_trex
from nfvo import sol006_VNFbuilder, sol006_NSD_builder, get_ns_vld_ip
from main import *
from utils.util import *
from typing import Union, Dict

# Insert functions to work with db(mango db)
db = persistency.db()
logger = create_logger('trexBlueprint')

# log into osm with user and pass
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)


class Trex(BlueprintBase):
    """
    The goal of this blueprint is to create TRex virtual machine regarding the input variables. It create and modify the
    configurations files inside the machine and run it.
    """

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None):
        BlueprintBase.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
        """
        conf["blueprint_instance_id"] = id_ 
        conf : input configurations
        """
        logger.info("Creating trex Blueprint")
        self.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [{'method': 'init_trex_day2_conf', 'callback': 'get_trex_results'}],
                'dayN': []
            }]
        }
        self.onboarded = False
        self.primitives = []
        # self.vnfd = {'core': [], 'tac': []}
        self.vnfd = {'core': []}

        core_area = next((item for item in self.conf['areas'] if item['core']), None)
        if core_area:
            self.conf['config']['core_area'] = core_area
        else:
            raise ValueError('Core area not found in the input')

    # day 0 operation to create vnf
    def bootstrap_day0(self, msg: dict) -> list:
        """
        msg : is the conf input
        """
        # we can ignore terraform part
        # self.vim_terraform(msg)
        return self.nsd()

    def nsd(self) -> list:

        logger.info("Creating trex Network Service Descriptors")
        nsd_names = []
        logger.info("building trex NSD")

        param = {
            'name': 'trex_' + str(self.get_id()),
            'id': 'trex_' + str(self.get_id()),
            "type": "trex"
        }
        vim_net_mapping = [
            {'vld': 'mgt', 'vim_net': self.conf['config']['network_endpoints']['mgt'], "mgt": True}]

        """
          I added vim as an input for adding networks numbers
        """
        # adding extra nets taking from inputs post message
        # and check if it is in the extra-nets input post message field
        try:
            for nets in self.conf['config']['network_endpoints']["data_nets"]:
                vim_net_mapping.append(
                    {'vld': 'data_{}'.format(nets['name']), 'vim_net': nets['name'], "mgt": False})
        except Exception:
            raise ValueError("Trex needs at least two (or multiplication of 2 ) extra networks defined in extra-nets")
        # First create vnfd for trex
        self.setVnfd('core', vld=vim_net_mapping)

        # Second step create NSD using function without template
        # get-id() ==> conf["blueprint_instance_id"]

        n_obj = sol006_NSD_builder(
            self.getVnfd('core'), self.get_vim_name(self.conf['config']['core_area']), param, vim_net_mapping
        )
        self.nsd_.append(n_obj.get_nsd())
        nsd_names.append(param["name"])
        # for v in self.conf['vims']:
        #     if 'tacs' in v:
        #         for b in v['tacs']:
        #             if type(b['id']) is int:
        #                 b['id'] = str(b['id'])
        #             logger.info(
        #                 "Creating K8s Worker Service Descriptors on VIM {} with TAC {}".format(v['name'], b['id']))
        #             nsd_names.append(self.worker_nsd(b, v))

        logger.info("NSDs created")
        return nsd_names

    def setVnfd(self, area, vld=None):
        '''
        This function used to set vnf descriptor for the given area, in my case "core"
        :param area: For TRex always set to "core"
        :param vld: equal to vim_net_mapping. adding extra nets taking from inputs post message
        :return:
        '''

        logger.debug("setting VNFd for " + area)
        if area == "core":
            if vld is None:
                raise ValueError("vlds are None in setVnfd")

            # Adding interfaces
            interfaces = []
            intf_index = 3  # starting from ens3
            for l_ in vld:
                interfaces.append(
                    {
                        "vld": l_["vld"],
                        "name": "ens{}".format(intf_index),
                        "mgt": l_["mgt"],
                        "port-security-enabled": False
                    }
                )
                intf_index += 1

            logger.info(f"interfaces are: {interfaces}")
            if len(interfaces) < 8:
                vir_cpu = '8'
            else:
                vir_cpu = f'{len(interfaces)}'

            vnfd = sol006_VNFbuilder({
                'username': 'root',
                'password': 'root',
                'id': self.get_id() + 'trex',
                'name': self.get_id() + 'trex',
                'vdu': [{
                    'count': 1,
                    'id': 'VM',
                    'image': 'ubuntu1804',
                    'vm-flavor': {'memory-mb': '8192', 'storage-gb': '10', 'vcpu-count': vir_cpu},
                    'interface': interfaces
                }]}, charm_name='flexcharm', cloud_init=True)
            self.vnfd['core'].append({'id': 'vnfd', 'name': vnfd.get_id(), 'vl': interfaces})

            logger.debug(self.vnfd)
        else:
            raise ValueError("area should be core in vfnd for trex")

    def getVnfd(self, area):
        if area == "core":
            logger.debug(self.vnfd['core'])
            return self.vnfd['core']

    def get_ip(self) -> None:
        logger.debug('getting IP addresses from vnf instances')

        if 'config' not in self.conf:
            self.conf['config'] = {}

        for n in self.nsd_:
            vlds = get_ns_vld_ip(n['nsi_id'], ['mgt'])
            self.conf['config']['trex_ip'] = vlds["mgt"][0]['ip']

        self.to_db()

    # Day 2 operations
    def init_trex_day2_conf(self, msg):
        logger.debug("Triggering Day2 Config for trex blueprint " + str(self.get_id()))
        res = []
        conf_ = Configurator_trex('trex_' + str(self.get_id()), 1, self.get_id(), self.conf).dump()
        # saving the id of the action because we need to post process its output
        self.action_to_check.append(conf_[0]['primitive_data']['primitive_params']['config-content'])
        res += conf_
        logger.debug("trex configuration built")

        self.to_db()
        return res

    def get_trex_results(self, callback_msg):
        # pass
        for primitive in callback_msg:
            if primitive['result']['charm_status'] != 'completed':
                raise ValueError('in Trex blue callback --> VNFM status is not completed')

            logger.warn(primitive)
            playbook_name = \
                primitive['primitive']['primitive_data']['primitive_params']['config-content']['playbooks'][0]['name']
            action_id = primitive['primitive']['primitive_data']['primitive_params']['config-content']['action_id']

            action_output = db.findone_DB('action_output', {'action_id': action_id})
            if not action_output:
                raise ValueError('Blue {}: output not found for action {}'.format(self.get_id(), action_id))
            logger.debug('**** retrieved action_output {}'.format(action_id))

            # retrieve data from action output
            self.conf['results_file'] = \
                parse_ansible_output(action_output, playbook_name, 'return trex results', 'msg')['stdout']

            logger.info(f"{self.conf['results_file']}")
        self.to_db()

    def _destroy(self):
        pass
