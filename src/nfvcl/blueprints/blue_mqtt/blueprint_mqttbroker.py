from nfvcl.blueprints import BlueprintBase
from nfvcl.utils import persistency
from nfvcl.nfvo import sol006_VNFbuilder, sol006_NSD_builder
from nfvcl.nfvo.osm_nbi_util import get_osm_nbi_utils
from nfvcl.utils.log import create_logger
from .models import MqttRequestBlueprintInstance
from typing import Union, Dict

db = persistency.DB()
logger = create_logger('MQTT Broker')
nbiUtil = get_osm_nbi_utils()


class MqttBroker(BlueprintBase):
    @classmethod
    def rest_create(cls, msg: MqttRequestBlueprintInstance):
        return cls.api_day0_function(msg)

    @classmethod
    def rest_upgrade(cls, msg: MqttRequestBlueprintInstance, blue_id: str):
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def day2_methods(cls):
        cls.api_router.add_api_route("/{blue_id}/upgrade", cls.rest_upgrade, methods=["PUT"])

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None):
        BlueprintBase.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
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

    def bootstrap_day0(self, msg: dict) -> list:
        return self.nsd()

    def setVnfd(self, interfaces: list):
        vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
            'id': '{}_mqtt_broker'.format(self.get_id()),
            'name': '{}_mqtt_broker'.format(self.get_id()),
            'kdu': [{
                'name': 'mqtt_broker',
                'helm-chart': 'nfvcl/mqttbroker',
                'interface': interfaces
            }]})
        self.vnfd["area"] = {'id': 'mqtt_broker', 'name': vnfd.get_id(), 'vl': interfaces}
        logger.debug(self.vnfd)

    def getVnfd(self):
        return self.vnfd["area"]

    def broker_nsd(self, area: dict) -> str:
        logger.info("Blue {} building NSD".format(self.get_id()))

        vnf_interfaces = [
            {
                'vld': 'data',
                'mgt': True,
                'k8s-cluster-net': 'data_net',
                'vim_net': self.conf['config']['network_endpoints']['data']
            },
        ]

        self.setVnfd(vnf_interfaces)

        param = {
            'name': 'mqtt_broker_' + str(self.get_id()),
            'id': 'mqtt_broker_' + str(self.get_id()),
            'type': 'mqtt_broker'
        }
        # tag, tac, list of vnf interfaces
        n_obj = sol006_NSD_builder([self.getVnfd()], self.get_vim_name(area['id']), param, vnf_interfaces)
        n_ = n_obj.get_nsd()
        self.nsd_.append(n_)

        return param['name']

    def nsd(self) -> list:
        logger.info("Creating MQTT Broker Network Service Descriptors")
        nsd_names = []
        # one router per nsd per tac
        for area in self.conf['areas']:
            logger.info("Creating MQTT Broker NSD on area {}".format(area['id']))
            nsd_names.append(self.broker_nsd(area))
        logger.info("NSDs created")
        return nsd_names

    def get_ip(self):
        self.to_db()

    def _destroy(self):
        pass
