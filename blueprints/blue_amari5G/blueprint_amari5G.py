import typing
from blueprints.blueprint import BlueprintBase
from blueprints.blue_5g_base import Blue5GBase
from configurators.amari5GC_configurator import Configurator_Amari5GC
from abc import ABC
from nfvo.vnf_manager import sol006_VNFbuilder
from nfvo.nsd_manager import sol006_NSD_builder, get_ns_vld_ip
from main import *

db = persistency.db()
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)
# create logger
logger = create_logger('Amari5GBlue')


class Amari5G(Blue5GBase, ABC):
    def __init__(self, conf: dict, id_: str, data: typing.Union[typing.Dict, None] = None) -> None:
        BlueprintBase.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
        logger.info("Creating Amari5G Blueprint")
        self.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [{'method': 'init_day2_conf'}],
                'dayN': []
            }],
            'add_tac': [{
                'day0': [{'method': 'add_tac_nsd'}],
                'day2': [{'method': 'add_tac_conf'}],
                'dayN': []
            }],
            'del_tac': [{
                'day0': [],
                'day2': [],
                'dayN': [{'method': 'del_tac'}]
            }],
            'add_slice': [{
                'day0': [],
                'day2': [{'method': 'add_slice_conf'}],
                'dayN': []
            }],
            'del_slice': [{
                'day0': [],
                'day2': [{'method': 'del_slice_conf'}],
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
        self.vnfd = {'core': [], 'tac': []}
        self.vim_core = next((item for item in self.conf['vims'] if item['core']), None)
        if self.vim_core is None:
            raise ValueError('Vim CORE not found in the input')

    def set_coreVnfd(self, area: str, vls=None) -> None:
        vnfd = sol006_VNFbuilder({
            'username': 'root',
            'password': 'root',
            'id': self.get_id() + '_amarisoft_5gc',
            'name': self.get_id() + '_amarisoft_5gc',
            'vdu': [{
                'count': 1,
                'id': 'VM',
                'image': 'amari5GC',
                'vm-flavor': {'memory-mb': '4096', 'storage-gb': '0', 'vcpu-count': '4'},
                'interface': vls,
                'vim-monitoring': True
            }]}, charm_name='flexcharm')
        self.vnfd['core'].append({'id': 'vnfd', 'name': vnfd.get_id(), 'vl': vls})
        logger.info(self.vnfd)

    def set_edgeVnfd(self, area: str, tac: int = 0, vim: dict = None) -> None:
        pass

    def setVnfd(self, area: str, tac: int = 0, vls: list = None, pdu: dict = None) -> None:
        logger.info("setting VNFd for " + area)
        if area == "core":
            self.set_coreVnfd(area, vls=vls)
        if area == 'tac':
            if tac is None:
                raise ValueError("tac is None in set Vnfd")
            list_ = []

            vnfd = sol006_VNFbuilder({
                'id': str(self.get_id()) + '_' + pdu['implementation'] + "_tac" + str(tac) + '_enb',
                'name': pdu['implementation'] + "_tac" + str(tac) + '_enb_pnfd',
                'pdu': [{
                    'count': 1,
                    'id': pdu['name'],
                    'interface': pdu['interface']
                # }]})
                }]}, charm_name='helmflexvnfm')
            list_.append({'id': 'enb_vnfd', 'name': vnfd.get_id(), 'vl': pdu['interface']})
            self.vnfd['tac'].append({'tac': tac, 'vnfd': list_})

    def getVnfd(self, area: str, tac: typing.Optional[str] =None) -> list:
        if area == "core":
            logger.debug(self.vnfd['core'])
            return self.vnfd['core']
        if area == "tac":
            if tac is None:
                raise ValueError("tac is None in getVnfd")
            tac_obj = next((item for item in self.vnfd['tac'] if item['tac'] == tac), None)
            if tac_obj is None:
                raise ValueError("tac not found in getting Vnfd")
            return tac_obj['vnfd']

    def core_nsd(self) -> str:
        logger.info("Creating Core NSD(s)")
        core_v = next((item for item in self.conf['vims'] if item['core']), None)
        vim_net_mapping = [
            {'vld': 'mgt', 'vim_net': core_v['mgt'], 'name': 'ens3', "mgt": True},
            {'vld': 'data', 'vim_net': core_v['wan']['id'], 'name': 'ens4', "mgt": False}
        ]
        self.setVnfd('core', vls=vim_net_mapping)
        param = {
            'name': '5GC_' + str(self.conf['plmn']) + "_" + str(self.get_id()),
            'id': '5GC_' + str(self.conf['plmn']) + "_" + str(self.get_id()),
            'type': 'core'
        }
        n_obj = sol006_NSD_builder(self.getVnfd('core'), core_v, param, vim_net_mapping)
        nsd_item = n_obj.get_nsd()
        nsd_item['vld'] = vim_net_mapping
        self.nsd_.append(nsd_item)
        return param['name']

    def edge_nsd(self, tac:dict, vim: dict) -> typing.List[str]:
        """Override method"""
        return []

    def check_tacs(self, msg: dict) -> bool:
        # FIXME to be implemented
        return False

    def update_recursive(self, dict1, dict2):
        '''
        UPdate two config dictionary recursively
        :param dict1: first dictionary to be updated
        :param dict2: second dictionary which entries should be used
        :return:
        '''
        for k, v in dict2.items():
            if k not in dict1:
                dict1[k] = dict()
            if isinstance(v, dict):
                self.update_recursive(dict1[k], v)
            else:
                if isinstance(v, list):
                    dict1[k].extend(v)
                else:
                    dict1[k] = v

    def update_confvims(self, new_vims):
        for v in new_vims:
            if 'tacs' not in v:
                logger.info('VIM ' + v['name'] + 'has no TAC field. Skipping.')
                continue
            if not v['tacs']:
                logger.info('VIM ' + v['name'] + 'has no declared TACs. Skipping.')
                continue

            old_vim = next((item for item in self.conf['vims'] if item['name'] == v['name']), None)
            if old_vim is None:
                self.conf['vims'].append(v)
            else:
                #old_vim.update(v)
                self.update_recursive(old_vim, v)

    def del_tac(self, msg: dict) -> list:
        nsi_to_delete = []
        for v in msg['vims']:
            if 'tacs' in v:
                for b in v['tacs']:
                    # check if tac is present in conf and if we have a nsi
                    # v_index = next(index for index, item in enumerate(self.conf['vims']) if item['name'] == v['name'])
                    vim_conf = next((item for item in self.conf['vims'] if item['name'] == v['name']), None)
                    if vim_conf is None:
                        raise ValueError('vim not found')
                    t_index = next((index for index, item in enumerate(vim_conf['tacs']) if item['id'] == b['id']), None)
                    if t_index is None:
                        logger.info('TAC {} not found, continuing with further TAC items'.format(b['id']))
                        continue
                    vim_conf['tacs'].pop(t_index)
                    nsd_i = next((index for index, item in enumerate(self.nsd_) if item['tac'] == b['id'] and item['type'] == 'ran'), None)
                    if nsd_i is None:
                        raise ValueError('nsd not found')
                    nsi_to_delete.append(self.nsd_[nsd_i]['nsi_id'])
                    self.nsd_.pop(nsd_i)
        return nsi_to_delete

    def add_tac_nsd(self, msg: dict) -> typing.List[str]:
        # update current blue config with new data. The "pending" status is reflected in self.nsd_ status
        if self.check_tacs(msg):
            raise ValueError('TACs in msg already exist')
        self.update_confvims(msg['vims'])
        nsd_names = []
        for v in msg['vims']:
            if 'tacs' in v:
                for b in v['tacs']:
                    nsd_names.append(self.ran_nsd(b, v))
                    edge_n = self.edge_nsd(b, v)
                    nsd_names.extend(edge_n)
        return nsd_names

    def edge_day2_conf(self, arg: dict, nsd_item: dict) -> typing.List[str]:
        pass

    def add_tac_conf(self, msg: dict) -> list:
        res = []
        for msg_vim in msg['vims']:
            if 'tacs' in msg_vim:
                for msg_tac in msg_vim['tacs']:
                    nsd = None
                    for nsd_item in self.nsd_:
                        if nsd_item['type'] == 'ran':
                            if nsd_item['tac'] == msg_tac['id']:
                                nsd = nsd_item
                                break
                    if nsd is None:
                        raise ValueError('nsd for tac {} not found'.format(msg_tac['id']))
                    res += self.ran_day2_conf({'vim': msg_vim['name'], 'tac': msg_tac['id']}, nsd)
                    edge_res = self.edge_day2_conf({'vim': msg_vim['name'], 'tac': msg_tac['id']}, nsd)
                    if edge_res :
                        res += edge_res
        return res

    def del_tac_conf(self, msg: dict) -> list:
        pass

    def init_day2_conf(self, msg: dict) -> list:
        logger.info("Initializing Day2 configurations")
        logger.debug("init_day2_conf msg: {}".format(msg))
        res = []
        self.to_db()
        for n in self.nsd_:
            if n['type'] == 'core':
                # vnfd = self.getVnfd('core')[0]
                conf_obj = Configurator_Amari5GC(n['descr']['nsd']['nsd'][0]['id'], 1, self.get_id(), self.conf, n['vld'])
                self.vnf_configurator.append(conf_obj)
                res += conf_obj.dump()
            if n['type'] == 'ran':
                # if self.pnf is False:
                #    raise ValueError("PNF not supported in this blueprint instance")
                res += self.ran_day2_conf(msg, n)
        self.to_db()
        return res

    def add_slice_conf(self, msg: dict) -> list:
        # msg = {conf: {'plmn'=, 'sst'=, 'sd'=, 'qos_flows'=, 'tacs'=[]}}
        logger.info("Adding 5G slice(s)")
        res = []
        for configurator in self.vnf_configurator:
            # the operations are evaluated within the configurator
            # (e.g., the nb does add anything if there is not its tac)
            res += configurator.add_slice(msg['conf'])
        return res

    def del_slice_conf(self, msg: dict) -> list:
        # msg = {conf: {'plmn'=, 'sst'=, 'sd'=, 'qos_flows'=, 'tacs'=[]}}
        logger.info("Deleting 5G slice(s)")
        res = []
        for configurator in self.vnf_configurator:
            # the operations are evaluated within the configurator
            # (e.g., the nb does add anything if there is not its tac)
            res += configurator.add_slice(msg['conf'])
        return res

    def get_ip_core(self, n) ->None:
        vlds = get_ns_vld_ip(n['nsi_id'], ["data", "mgt"])
        core_v = next((item for item in self.conf['vims'] if item['core']), None)
        self.conf['config']['core_wan_ip'] = vlds["data"][0]['ip']
        core_v['core_mgt_ip'] = vlds["mgt"][0]['ip']
        vnfd = self.getVnfd('core')[0]
        for vl in vnfd['vl']:
            if vl['vld'] == 'mgt':
                vl['ip'] = vlds["mgt"][0]['ip'] + '/24'
            if vl['vld'] == 'data':
                vl['ip'] = vlds["data"][0]['ip'] + '/24'

    def get_ip(self) -> None:
        logger.info('Getting IP addresses of VNFIs')
        for n in self.nsd_:
            if n['type'] == 'core':
                self.get_ip_core(n)

            if n['type'] == 'ran':
                try:
                    vim = next((item for item in self.conf['vims'] if item['name'] == n['vim']), None)
                    if vim is None:
                        raise ValueError("get_ip vim is None")
                    tac = next((item for item in vim['tacs'] if item['id'] == n['tac']), None)
                    if tac is None:
                        raise ValueError("get_ip tac is None")

                    logger.info('Setting IP addresses for RAN nsi for TAC {} on VIM {}'.format(tac['id'], vim['name']))

                    # retrieving vlds from the vnf
                    vnfd = self.getVnfd('tac', tac['id'])[0]
                    vld_names = [i['vld'] for i in vnfd['vl']]
                    vlds = get_ns_vld_ip(n['nsi_id'], vld_names)

                    if len(vld_names) == 1:
                        #this enb has only one interface, by definition it should be labelled as mgt
                        tac['nb_wan_ip'] = vlds["mgt"][0]['ip']
                        tac['nb_mgt_ip'] = vlds["mgt"][0]['ip']
                    elif 'data' in vld_names:
                        # this enb has a separate data-plane interface
                        tac['nb_wan_ip'] = vlds["data"][0]['ip']
                        tac['nb_mgt_ip'] = vlds["mgt"][0]['ip']
                    else:
                        raise ValueError('mismatch in the enb interfaces')
                except Exception as e:
                    logger.error("Exception in getting IP addresses from RAN nsi: " + str(e))
                    raise ValueError(str(e))
        self.to_db()

    def _destroy(self):
        logger.info("Destroying")

        if hasattr(self, 'overlay_ipd'):
            self.overlay_ipd.release_all(self.conf['plmn'])
