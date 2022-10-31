from blueprints.blueprint import BlueprintBase
# from blueprints.blueprint_utils import parse_ansible_output
from utils import persistency
from nfvo.vnf_manager import sol006_VNFbuilder
from nfvo.nsd_manager import sol006_NSD_builder, get_ns_vld_ip
# import jinja2
from configurators.vyos_configurator import Configurator_VyOs
from utils.util import *

db = persistency.db()
logger = create_logger('VyOSBlue')

# one router per tac
# multiple interfaces per router
# each router could have a different number of interfaces

class VyOSBlue(BlueprintBase):
    def __init__(self, conf: dict, id_: str, recover=False):
        BlueprintBase.__init__(self, conf, id_)
        logger.info("Creating VyOS Blueprint")
        self.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [{'method': 'init_day2_conf'}],
                'dayN': []
            }],
            'add_router': [{
                'day0': [{'method': 'add_router'}],
                'day2': [{'method': 'add_router_day2'}],
                'dayN': []
            }],
            'del_router': [{
                'day0': [],
                'day2': [{'method': 'del_router'}],
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
        self.vnfd = {'tac': []}

    def bootstrap_day0(self, msg: dict) -> list:
        return self.nsd()

    def setVnfd(self, vnf_tag, tac, interfaces):
        if vnf_tag is 'VyOS':
            vnfd = sol006_VNFbuilder({
                'username': 'vyos',
                'password': 'vyos',
                'id': self.get_id() + '_vyos_' + str(tac['id']),
                'name': self.get_id() + '_vyos_' + str(tac['id']),
                'vdu': [{
                    'count': 1,
                    'id': 'VM',
                    'image': 'VyOS',
                    'vm-flavor': {'memory-mb': '1024', 'storage-gb': '10', 'vcpu-count': '2'},
                    'interface': interfaces
                }]}, charm_name='flexcharmvyos')
        self.vnfd['tac'].append({'id': vnf_tag, 'name': vnfd.get_id(), 'tac_id': tac['id'], 'vl': interfaces})
        logger.info(self.vnfd)

    def getVnfd(self, tac_id: int):
        vnfd_ref = next((item for item in self.vnfd['tac'] if item['tac_id'] == tac_id), None)
        return vnfd_ref

    def router_nsd(self, tac: dict, vim: dict) -> str:
        logger.info("building NSD for tac " + str(tac['id']))

        vnf_interfaces = tac['interfaces']  # no need to filter per vnf: they are all attached to the router
        for vld in vnf_interfaces:
            if not vld['mgt']:
                # it's a router, let's disable OS port security
                vld['port-security-enabled'] = False
        self.setVnfd('VyOS', tac, vnf_interfaces)

        vim_net_mapping = tac['interfaces']
        param = {
            'name': 'router_tac_' + str(tac['id']) + '_' + str(self.get_id()),
            'id': 'router_tac_' + str(tac['id']) + '_' + str(self.get_id()),
            'type': 'router'
        }
        # tag, tac, list of vnf interfaces
        n_obj = sol006_NSD_builder([self.getVnfd(tac['id'])], vim, param, vim_net_mapping)
        n_ = n_obj.get_nsd()
        n_['tac'] = tac['id']
        self.nsd_.append(n_)
        return param['name']

    def nsd(self) -> list:
        logger.info("Creating VyOS Network Service Descriptors")
        nsd_names =[]
        # one router per nsd per tac
        for v in self.conf['vims']:
            if 'tacs' in v:
                for b in v['tacs']:
                    logger.info("Creating VyOS vnfd on VIM {} with TAC {}".format(v['name'], b['id']))
                    nsd_names.append(self.router_nsd(b, v))
        logger.info("NSDs created")
        return nsd_names

    def init_day2_conf(self, msg: dict) -> list:
        logger.debug("Triggering Day2 Config for VyOS blueprint " + str(self.get_id()))
        res = []
        for nsd_item in self.nsd_:
            # create the initial config of routers
            data_for_router = None
            for v in self.conf['vims']:
                for b in v['tacs']:
                    if b['id'] == nsd_item['tac']:
                        data_for_router = b
            if data_for_router is None:
                raise ValueError('no config data for router ' + nsd_item['tac'] + " has been found!")

            config = Configurator_VyOs(
                nsd_item['descr']['nsd']['nsd'][0]['id'],
                1,
                self.get_id(),
                data_for_router
            ).dump()
            res += config
        '''
        conf_ = Configurator_K8s('k8s_controller_' + str(self.get_id()), 1, self.get_id(), self.conf,
                                 role='master').dump()
        # saving the id of the action because we need to post process its output
        self.action_to_check.append(conf_[0]['param_value']['action_id'])
        res += conf_
        logger.debug("K8s master configuration built")
        '''
        self.save_conf()
        return res

    def add_router(self, msg) -> list:
        logger.debug("Add router to VyOS blueprint " + str(self.get_id()))
        nsd_names = []
        if 'vims' not in msg:
            raise ValueError("vims not in msg VyOS add_router")

        for msg_vim in msg['vims']:
            # check if the vim is already in conf
            conf_vim_ = next((item for item in self.conf['vims'] if item['name'] == msg_vim['name']), None)
            if conf_vim_ is None:
                self.conf['vims'].append(conf_vim_)
                conf_vim_ = self.conf['vims'][-1]

            if 'tacs' in msg_vim:
                for msg_b in msg_vim['tacs']:
                    # check if tac is already existing in self_conf
                    conf_tac_ = next((item for item in conf_vim_['tacs'] if item['id'] == msg_b['id']), None)
                    if conf_tac_ is not None:
                        raise ValueError("VyOS add_router TAC already existing")
                    conf_vim_['tacs'].append(msg_b)
                    logger.info("Creating VyOS Service Descriptors on VIM {} with TAC {}".format(msg_vim['name'],
                                                                                                       msg_b['id']))
                    nsd_names.append(self.router_nsd(msg_b, msg_vim))

        return nsd_names

    def add_router_day2(self, msg):
        res = []

        '''
        for msg_vim in msg['vims']:
            if 'tacs' in msg_vim:
                for msg_tac in msg_vim['tacs']:
                    conf_ = Configurator_K8s(
                        'k8s_worker_tac_' + msg_tac['id'] + '_' + str(self.get_id()),
                        1,
                        self.get_id(),
                        self.conf,
                        role='worker',
                        master_key=self.conf['master_key_add_worker']
                    ).dump()
                    # saving the id of the action because we need to post process its output
                    # self.action_to_check.append(conf_[0]['param_value']['action_id'])
                    res += conf_
        logger.debug("K8s master configuration built")
        '''
        self.save_conf()
        return res

    def get_ip(self):
        logger.info('getting IP addresses from vnf instances')
        if 'config' not in self.conf:
            self.conf['config'] = {}

        for n in self.nsd_:
            logger.debug("now analyzing nsi {}".format(n['nsi_id']))
            for v in self.conf['vims']:
                if 'tacs' in v:
                    for b in v['tacs']:
                        logger.debug("now analyzing tac {} for nsi {}".format(b['id'], n['nsi_id']))
                        if b['id'] == n['tac']:
                            for i in b['interfaces']:
                                vl_item = get_ns_vld_ip(n['nsi_id'], [i['vld']])
                                i['ip_address'] = vl_item[i['vld']][0]['ip']
                                logger.info("tac {}, vld_name {}, ip: {}".format(b['id'], i['vld'], i['ip_address']))
                            break
        self.save_conf()

    def destroy(self):
        logger.info("Destroying")
        self.del_conf()


