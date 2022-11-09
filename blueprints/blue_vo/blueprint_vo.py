from blueprints import BlueprintBase
from .models import VoBlueprintRequestInstance
from nfvo import sol006_VNFbuilder, sol006_NSD_builder, get_kdu_services
from main import *
from typing import Union, Dict

db = persistency.DB()
logger = create_logger('VOBlue')
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)


class VO(BlueprintBase):
    @classmethod
    def rest_create(cls, msg: VoBlueprintRequestInstance):
        return cls.api_day0_function(msg)

    @classmethod
    def rest_upgrade(cls, msg: VoBlueprintRequestInstance, blue_id: str):
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def day2_methods(cls):
        cls.api_router.add_api_route("/{blue_id}", cls.rest_upgrade, methods=["PUT"])

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None):
        BlueprintBase.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
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
        vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
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

    def vo_nsd(self, area: dict) -> str:
        # fixme: annotate the helm chart with the area
        logger.info("Blue {} - building NSD".format(self.get_id()))

        vnf_interfaces = [
            {
                'vld': 'data',
                'mgt': True,
                'k8s-cluster-net': 'data_net',
                'vim_net': self.conf['config']['network_endpoints']['data']
            },
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
        n_obj = sol006_NSD_builder(
            [self.getVnfd()],
            self.get_vim_name(area['id']),
            param,
            vnf_interfaces,
            knf_configs=knf_configs
        )
        n_ = n_obj.get_nsd()
        self.nsd_.append(n_)

        return param['name']

    def nsd(self) -> list:
        logger.info("Creating Virtual Object Network Service Descriptors")
        nsd_names = []
        # one router per nsd per tac
        for area in self.conf['areas']:
            logger.info("Creating Virtual Object NSD on area {}".format(area['id']))
            nsd_names.append(self.vo_nsd(area))
        logger.info("NSDs created")
        self.to_db()
        return nsd_names

    def get_ip(self):
        kdu_services = get_kdu_services(self.nsd_[0]['nsi_id'], 'vo')
        self.conf['config']['external_ip'] = kdu_services[0]['external_ip'][0]
        # self.to_db()

    def destroy(self):
        logger.info("Destroying")
        self.to_db()


