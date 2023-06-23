from blueprints import BlueprintBase
from nfvo import sol006_VNFbuilder,  sol006_NSD_builder, get_ns_vld_ip, NbiUtil
from .configurators.ueransim_configurator import ConfiguratorUeUeRanSim
# from main import create_logger, nbiUtil
from utils import persistency
from utils.util import *
from typing import Union, Dict, Callable
from .models import UeranSimBlueprintRequestInstance
from fastapi import APIRouter

nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)
db = persistency.DB()
logger = create_logger('UeRanSim')


class UeRanSim(BlueprintBase):
    @classmethod
    def rest_create(cls, msg: UeranSimBlueprintRequestInstance):
        return cls.api_day0_function(msg)

    # Fixme: create the pydantic model for adding/removing UEs
    @classmethod
    def rest_add_del_ues(cls, msg: UeranSimBlueprintRequestInstance, blue_id: str):
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def day2_methods(cls):
        cls.api_router.add_api_route("/{blue_id}/ues", cls.rest_add_del_ues, methods=["PUT"])

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None):
        BlueprintBase.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
        logger.info("Creating UeRanSim Blueprint")
        self.supported_operations = {
            'init': [{'day0': [{'method': 'bootstrap_day0'}], 'day2': [{'method': 'init_day2_conf'}], 'dayN': []}],
            'add_ue': [{'day0': [{'method': 'add_ue'}], 'day2': [{'method': 'add_ue_day2'}], 'dayN': []}],
            'del_ue': [{'day0': [], 'day2': [{'method': 'del_ue'}], 'dayN': []}],
            'add_nb': [{'day0': [{'method': 'add_ue'}], 'day2': [{'method': 'add_ue_day2'}], 'dayN': []}],
            'del_nb': [{'day0': [], 'day2': [{'method': 'del_ue'}], 'dayN': []}],
            'monitor': [{'day0': [], 'day2': [{'method': 'enable_prometheus'}], 'dayN': []}],
            'log': [{'day0': [], 'day2': [{'method': 'enable_elk'}], 'dayN': []}],
        }
        if not data:
            self.primitives = []
            self.vnfd = {'area': [], 'ue': []}
            self.pdu = []
        # FIXME: how to connect radionets among different vims??

    def vim_terraform(self, msg):
        net = {
            "name": "radio_{}".format(self.get_id()),
            "external": False,
            "type": "vxlan",
            "cidr": '10.168.0.0/16',
            "allocation_pool": [{'start': '10.168.0.2', 'end': '10.168.255.253'}],
            "gateway_ip": None,
            "enable_dhcp": True,
            "dns_nameservers": [],
            "host_routes": []
        }
        self.topology_add_network(net, msg['areas'])

    def bootstrap_day0(self, msg: dict) -> list:
        self.check_pdu_area(msg)
        self.conf = msg
        self.vim_terraform(msg)
        return self.nsd()

    def setVnfd(self, vnf_tag: str, interfaces: list, area=None, ue_id=None):
        if vnf_tag == 'UE':
            if ue_id is None:
                raise ValueError('UE id should be provided to build the VNFd')

            vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
                'username': 'root',
                'password': 'root',
                'id': self.get_id() + '_ue_' + str(ue_id),
                'name': self.get_id() + '_ue_' + str(ue_id),
                'vdu': [{
                    'count': 1,
                    'id': 'VM',
                    'image': 'ueransim_v2.1',
                    'vm-flavor': {'memory-mb': '4096', 'storage-gb': '8', 'vcpu-count': '2'},
                    'interface': interfaces,
                    'vim-monitoring': True
                }]}, charm_name='helmflexvnfm')
            self.vnfd['ue'].append(
                {'id': '{}'.format(ue_id), 'name': vnfd.get_id(), 'vl': interfaces})

        elif vnf_tag == 'NB':
            if area is None:
                raise ValueError('NB area should be provided to build the VNFd')

            vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
                'username': 'root',
                'password': 'root',
                'id': self.get_id() + '_nb_' + str(area['id']),
                'name': self.get_id() + '_nb_' + str(area['id']),
                'vdu': [{
                    'count': 1,
                    'id': 'VM',
                    'image': 'ueransim_v2.1',
                    'vm-flavor': {'memory-mb': '4096', 'storage-gb': '8', 'vcpu-count': '2'},
                    'interface': interfaces,
                    'vim-monitoring': True
                }]}, charm_name='helmflexvnfm')
            self.vnfd['area'].append(
                {'id': vnf_tag, 'name': vnfd.get_id(), 'area_id': area['id'], 'vl': interfaces})

        logger.info(self.vnfd)

    def getVnfd(self, vnf_tag: str, area_id=None, ue_id=None):
        if ue_id is None:
            vnfd_ref = next(
                (item for item in self.vnfd['area'] if item['area_id'] == area_id and item['id'] == vnf_tag), None)
        else:
            vnfd_ref = next((item for item in self.vnfd['ue'] if item['id'] == str(ue_id)), None)
        return vnfd_ref

    def nb_nsd(self, area: dict) -> str:
        logger.info("building NB NSD for area " + str(area['id']))
        if self.conf['config']['network_endpoints']['mgt'] == self.conf['config']['network_endpoints']['wan'] or \
                not self.conf['config']['network_endpoints']['wan']:
            area['vnf_interfaces'] = [
                {"vim_net": self.conf['config']['network_endpoints']['mgt'], "vld": "mgt", "name": "ens3", "mgt": True},
                {"vim_net": "radio_{}".format(self.get_id()), "vld": "radionet", "name": "ens5", "mgt": False}
            ]
        else:
            area['vnf_interfaces'] = [
                {"vim_net": self.conf['config']['network_endpoints']['mgt'], "vld": "mgt", "name": "ens3",
                 "mgt": True},
                {"vim_net": self.conf['config']['network_endpoints']['wan'], "vld": "datanet", "name": "ens4",
                 "mgt": False},
                {"vim_net": "radio_{}".format(self.get_id()), "vld": "radionet", "name": "ens5", "mgt": False}
            ]
        self.setVnfd('NB', area['vnf_interfaces'], area=area)

        param = {
            'name': '{}_nb_tac_{}'.format(self.get_id(), area['id']),
            'id': '{}_nb_tac_{}'.format(self.get_id(), area['id']),
            'type': 'nb'
        }
        # tag, tac, list of vnf interfaces
        vnfd = self.getVnfd('NB', area_id=area['id'])
        logger.warn(vnfd)
        n_obj = sol006_NSD_builder([vnfd], self.get_vim_name(area), param, area['vnf_interfaces'])
        n_ = n_obj.get_nsd()
        n_['area'] = area['id']
        self.nsd_.append(n_)
        return param['name']

    def ue_nsd(self, ue: dict, area: dict) -> str:
        logger.info("building NSD for UE " + str(ue['id']))
        ue['vnf_interfaces'] = [
            {"vim_net": self.conf['config']['network_endpoints']['mgt'], "vld": "mgt", "name": "ens3", "mgt": True},
            {"vim_net": "radio_{}".format(self.get_id()), "vld": "radionet", "name": "ens4", "mgt": False}
        ]
        self.setVnfd('UE', ue['vnf_interfaces'], ue_id=ue['id'])

        param = {
            'name': '{}_ue_{}'.format(self.get_id(), ue['id']),
            'id': '{}_ue_{}'.format(self.get_id(), ue['id']),
            'type': 'ue'
        }
        # tag, tac, list of vnf interfaces
        n_obj = sol006_NSD_builder(
            [self.getVnfd('UE', ue_id=ue['id'])], self.get_vim_name(area['id']), param, ue['vnf_interfaces'])
        n_ = n_obj.get_nsd()
        n_['ue_id'] = ue['id']
        self.nsd_.append(n_)
        return param['name']

    def nsd(self) -> list:
        logger.info("Creating UeRanSim Network Service Descriptors")
        nsd_names = []

        for area in self.conf['areas']:
            logger.info("Creating UeRanSim NB vnfd on area {}".format(area['id']))
            nsd_names.append(self.nb_nsd(area))

            for ue in area['ues']:
                logger.info("Creating UeRanSim UE vnfd on area {} with ID {}".format(area['id'], ue['id']))
                nsd_names.append(self.ue_nsd(ue, area))
        logger.debug("NSDs created")
        return nsd_names

    def check_pdu_area(self, msg: dict):
        for area in msg['areas']:
            if self.topology_get_pdu_by_area(area):
                self.status = 'error'
                self.detailed_status = 'PDU at area {} already existing'.format(area['id'])
                raise ValueError(self.detailed_status)

    def init_day2_conf(self, msg: dict) -> list:
        logger.info("triggering day2 operations for ueransim blueprint with id {}".format(self.get_id()))
        res = []
        gnb_radio_ips = []
        # before we have to get info from all the NodeBs (IP address on the radio interface), then we can pass to UEs
        for nsd_item in self.nsd_:
            # create the initial config of routers
            if nsd_item['type'] == 'nb':
                for area in self.conf['areas']:
                    if 'area' in nsd_item and area['id'] == nsd_item['area']:
                        pdu_check = self.topology_get_pdu_by_area(area['id'])
                        if pdu_check:
                            self.status = 'error'
                            self.detailed_status = 'PDU at area {} already existing'.format(area['id'])
                            self.to_db()
                            raise ValueError(self.detailed_status)

                        pdu_interfaces = []
                        for intf in area['vnf_interfaces']:
                            # radio emulation net should not be added to the pdu, which, like real NBs, should
                            # have only mgt and data links
                            if intf['vld'] != 'radionet':
                                pdu_interfaces.append(
                                    {
                                        'vld': intf['vld'],
                                        'name': intf['name'],
                                        'ip-address': intf['ip-address'],
                                        'vim-network-name': intf['vim_net'],
                                        'mgt': True if intf['vld'] == 'mgt' else False
                                    }
                                )
                            if intf['vld'] == "radionet":
                                gnb_radio_ips.append(intf['ip-address'])
                        #################### from here
                        # NOTE the actual config of the NB will be pushed later, we are preparing only the pnf here

                        #FIXME: validete against the pdu pydantic model
                        pdu_obj = {
                            'name': 'nb_{}'.format(area['id']),
                            'area': str(area['id']),
                            'type': 'nb'.format(area['id']),
                            'user': 'root',
                            'passwd': 'root',
                            'implementation': "ueransim_nb",
                            'nfvo_onboarded': False,
                            'config': {'cell_id': '{}'.format(hex(1000 + area['id'])), 'radio_addr': gnb_radio_ips[-1]},
                            'interface': pdu_interfaces
                        }

                        self.topology_add_pdu(pdu_obj)

        # now lets configure UEs
        for nsd_item in self.nsd_:
            if nsd_item['type'] == 'ue':
                for area in self.conf['areas']:
                    for ue in area['ues']:
                        ue['vim_gnbs_ips'] = gnb_radio_ips
                        if 'ue_id' in nsd_item and ue['id'] == nsd_item['ue_id']:
                            config = ConfiguratorUeUeRanSim(
                                        nsd_item['descr']['nsd']['nsd'][0]['id'],
                                        1,
                                        self.get_id(),
                                        ue
                                    ).dump()
                            res += config

        self.to_db()
        return res

    def add_ue(self, msg) -> list:
        logger.debug("Adding UE(s) to UeRanSim blueprint " + str(self.get_id()))
        nsd_names = []
        for msg_vim in msg['ues']:
            conf_vim_ = next((item for item in self.conf['vims'] if item['name'] == msg_vim['name']), None)
            if conf_vim_ is None:
                self.conf['vims'].append(conf_vim_)
                conf_vim_ = self.conf['vims'][-1]

            if 'areas' in msg_vim:
                for msg_b in msg_vim['tacs']:
                    # check if tac is already existing in self_conf
                    conf_tac_ = next((item for item in conf_vim_['tacs'] if item['id'] == msg_b['id']), None)
                    if conf_tac_ is not None:
                        raise ValueError("VyOS add_router TAC already existing")
                    conf_vim_['tacs'].append(msg_b)
                    logger.info("Creating VyOS Service Descriptors on VIM {} with TAC {}".format(msg_vim['name'],
                                                                                                 msg_b['id']))
                    nsd_names.append(self.ue_nsd(msg_b, msg_vim))

        return nsd_names

    def get_ip(self):
        logger.info('getting IP addresses from vnf instances')
        for n in self.nsd_:
            logger.debug("now analyzing nsi {}".format(n['nsi_id']))

            for area in self.conf['areas']:
                logger.debug("now analyzing area {} for nsi {}".format(area['id'], n['nsi_id']))
                if 'area' in n and area['id'] == n['area']:
                    vl_items = get_ns_vld_ip(n['nsi_id'], ["datanet", "radionet", "mgt"])
                    logger.debug(vl_items)
                    for intf in area['vnf_interfaces']:
                        intf['ip-address'] = vl_items[intf['vld']][0]['ip']

                for ue in area['ues']:
                    logger.debug("now analyzing ue {} for nsi {}".format(area['id'], n['nsi_id']))
                    if 'ue_id' in n and ue['id'] == n['ue_id']:
                        vl_items = get_ns_vld_ip(n['nsi_id'], ["radionet", "mgt"])
                        logger.debug(vl_items)
                        for intf in ue['vnf_interfaces']:
                            intf['ip-address'] = vl_items[intf['vld']][0]['ip']

        logger.info("VNFs' IP addresses acquired")
        self.to_db()

    def _destroy(self):
        logger.debug("Destroying UeRanSim specific resources")

        logger.debug("deleting radio net")
        area_ids = [item["id"] for item in self.conf["areas"]]

        net = {
            "name": "radio_{}".format(self.get_id()),
            "external": False,
            "type": "vxlan",
            "cidr": '10.168.0.0/16',
            "allocation_pool": [{'start': '10.168.0.2', 'end': '10.168.255.253'}],
            "gateway_ip": None,
            "enable_dhcp": True,
            "dns_nameservers": [],
            "host_routes": []
        }
        self.topology_del_network(net, area_ids)
