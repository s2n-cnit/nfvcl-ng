from blueprints.blueprint import BlueprintBase
from utils import persistency
from nfvo.vnf_manager import sol006_VNFbuilder
from nfvo.nsd_manager import sol006_NSD_builder, get_kdu_services
from utils.util import *

db = persistency.db()
logger = create_logger('VOBlue')

class VO(BlueprintBase):
    def __init__(self, conf: dict, id_: str, recover: bool = False):
        BlueprintBase.__init__(self, conf, id_)
        logger.info("Creating Virtual Object Blueprint")
        self.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [],
                'dayN': []
            }],
            'upgrade': [{
                'day0': [],
                'day2': [{'method': 'upgrade'}],
                'dayN': []
            }],
            'monitor': [{
                'day0': [],
                'day2': [{'method': 'enable_prometheus'}],
                'dayN': []
            }],
            'log': [{
                'day0': [],
                'day2': [{'method': 'enable_elk'}],
                'dayN': []
            }],
        }
        self.primitives = []
        self.vnfd = []

    def upgrade(self, msg: dict) -> list:
        pass

    def bootstrap_day0(self, msg: dict) -> list:
        return self.nsd()

    def setVnfd(self, interfaces: list):
        vnfd = sol006_VNFbuilder({
        'id': '{}_vo'.format(self.get_id()),
        'name': '{}_vo'.format(self.get_id()),
        'kdu': [{
            'name': 'vo',
            'helm-chart': 'nfvcl_helm_repo/vobject:0.0.10',
            'interface': interfaces
        }]})
        self.vnfd.append({'id': 'vo', 'name': vnfd.get_id(), 'vl': interfaces})
        logger.debug(self.vnfd)

    def getVnfd(self):
        return self.vnfd[0]

    def vo_nsd(self, vim: dict) -> str:
        logger.info("Blue {} building NSD".format(self.get_id()))

        vnf_interfaces = [
            {'vld': 'data', 'mgt': True, 'k8s-cluster-net': 'data_net', 'vim_net': vim['load_balancer_net']['id']},
        ]

        self.setVnfd(vnf_interfaces)

        if 'objectLinks' in self.conf['config']:
            #then it is not cVO
            #lets override the MQTT broker IP
            self.conf['config']['url'] = "tcp://{}:{}".format("192.168.25.128", 1883)

        knf_configs = [{
            'vnf_id': '{}_vo'.format(self.get_id()),
            'kdu_confs': [{'kdu_name': 'vo', "additionalParams": {
                "config": self.conf['config'],
                "image": {
                    "tag": "0.0.11",
                    "registry": "docker.io",
                    "repository": "smartssrl/ebrewery",
                    "pullPolicy": "IfNotPresent"
                }
                # "extIPaddress": "172.16.200.151"
            }}]
        }]

        param = {
            'name': 'vo_' + str(self.get_id()),
            'id': 'vo_' + str(self.get_id()),
            'type': 'vo'
        }
        # tag, tac, list of vnf interfaces
        n_obj = sol006_NSD_builder([self.getVnfd()], vim, param, vnf_interfaces, knf_configs=knf_configs)
        n_ = n_obj.get_nsd()
        self.nsd_.append(n_)

        return param['name']

    def nsd(self) -> list:
        logger.info("Creating Virtual Object Network Service Descriptors")
        nsd_names = []
        # one router per nsd per tac
        for v in self.conf['vims']:
            logger.info("Creating Virtual Object NSD on VIM {}".format(v['name']))
            nsd_names.append(self.vo_nsd(v))
        logger.info("NSDs created")
        self.save_conf()
        return nsd_names

    def get_ip(self):
        kdu_services = get_kdu_services(self.nsd_[0]['nsi_id'], 'vo')
        logger.debug("get_ip ---- kdu_services= {}".format(kdu_services))
        self.conf['config']['external_ip'] = kdu_services[0]['external_ip'][0]
        self.save_conf()

    def destroy(self):
        logger.info("Destroying")
        self.del_conf()


