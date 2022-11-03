from blueprints.blueprint import BlueprintBase
from utils import persistency
from nfvo.vnf_manager import sol006_VNFbuilder
from nfvo.nsd_manager import sol006_NSD_builder
from utils.util import *

db = persistency.DB()
logger = create_logger('MQTT Broker')


class MqttBroker(BlueprintBase):
    def __init__(self, conf: dict, id_: str, recover: bool = False):
        BlueprintBase.__init__(self, conf, id_)
        logger.info("Creating MQTT Broker")
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

    def bootstrap_day0(self, msg: dict) -> list:
        return self.nsd()

    def setVnfd(self, interfaces: list):
        vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
            'id': '{}_mqtt_broker'.format(self.get_id()),
            'name': '{}_mqtt_broker'.format(self.get_id()),
            'kdu': [{
                'name': 'mqtt_broker',
                'helm-chart': 'nfvcl_helm_repo/mqttbroker:0.0.2',
                'interface': interfaces
            }]})
        self.vnfd.append({'id': 'mqtt_broker', 'name': vnfd.get_id(), 'vl': interfaces})
        logger.debug(self.vnfd)

    def getVnfd(self):
        return self.vnfd[0]

    def broker_nsd(self, vim: dict) -> str:
        logger.info("Blue {} building NSD".format(self.get_id()))

        vnf_interfaces = [
            {'vld': 'data', 'mgt': True, 'k8s-cluster-net': 'data_net', 'vim_net': vim['load_balancer_net']['id']},
        ]

        self.setVnfd(vnf_interfaces)

        """
        knf_configs = [{
            'vnf_id': '{}_mqtt_broker'.format(self.get_id()),
            'kdu_confs': [{'kdu_name': 'mqtt_broker', "additionalParams": {
                "config": self.conf['config'],
                # "extIPaddress": "172.16.200.151"
            }}]
        }]
        """

        param = {
            'name': 'mqtt_broker_' + str(self.get_id()),
            'id': 'mqtt_broker_' + str(self.get_id()),
            'type': 'mqtt_broker'
        }
        # tag, tac, list of vnf interfaces
        n_obj = sol006_NSD_builder([self.getVnfd()], vim, param, vnf_interfaces)  #, knf_configs=knf_configs)
        n_ = n_obj.get_nsd()
        self.nsd_.append(n_)

        return param['name']

    def nsd(self) -> list:
        logger.info("Creating MQTT Broker Network Service Descriptors")
        nsd_names = []
        # one router per nsd per tac
        for v in self.conf['vims']:
            logger.info("Creating MQTT Broker NSD on VIM {}".format(v['name']))
            nsd_names.append(self.broker_nsd(v))
        logger.info("NSDs created")
        return nsd_names

    def get_ip(self):
        self.save_conf()

    def destroy(self):
        logger.info("Destroying")
        self.del_conf()
