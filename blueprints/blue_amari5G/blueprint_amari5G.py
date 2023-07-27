import typing
from blueprints import BlueprintBase
from blueprints.blue_5g_base import Blue5GBase
from .configurators.amari5GC_configurator import Configurator_Amari5GC
from blueprints.blue_5g_base.models import Create5gModel
from nfvo import sol006_VNFbuilder, sol006_NSD_builder, get_ns_vld_ip
from nfvo.osm_nbi_util import get_osm_nbi_utils
from utils.log import create_logger
from utils.persistency import DB

db = DB()
nbiUtil = get_osm_nbi_utils()
# create logger
logger = create_logger('Amari5GBlue')


class Amari5G(Blue5GBase):
    @classmethod
    def rest_create(cls, msg: Create5gModel):
        return cls.api_day0_function(msg)

    @classmethod
    def day2_methods(cls):
        # cls.api_router.add_api_route("/{blue_id}", cls.rest_scale, methods=["PUT"])
        pass

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

    def set_core_vnfd(self, area: str, vls=None) -> None:
        vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
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

    def set_edge_vnfd(self, area: str, tac: int = 0, vim: dict = None) -> None:
        pass

    def core_nsd(self) -> str:
        logger.info("Creating Core NSD(s)")
        core_v = next((item for item in self.conf['vims'] if item['core']), None)
        vim_net_mapping = [
            {'vld': 'mgt', 'vim_net': core_v['mgt'], 'name': 'ens3', "mgt": True},
            {'vld': 'data', 'vim_net': core_v['wan']['id'], 'name': 'ens4', "mgt": False}
        ]
        self.set_vnfd('core', vls=vim_net_mapping)
        param = {
            'name': '5GC_' + str(self.conf['plmn']) + "_" + str(self.get_id()),
            'id': '5GC_' + str(self.conf['plmn']) + "_" + str(self.get_id()),
            'type': 'core'
        }
        n_obj = sol006_NSD_builder(self.get_vnfd('core'), core_v, param, vim_net_mapping)
        nsd_item = n_obj.get_nsd()
        nsd_item['vld'] = vim_net_mapping
        self.nsd_.append(nsd_item)
        return param['name']

    def edge_nsd(self, tac:dict, vim: dict) -> typing.List[str]:
        """Override method"""
        return []

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
        self.update_confvims(msg['vims'])
        nsd_names = []
        for v in msg['vims']:
            if 'tacs' in v:
                for b in v['tacs']:
                    nsd_names.append(self.ran_nsd(b, v))
                    edge_n = self.edge_nsd(b, v)
                    nsd_names.extend(edge_n)
        return nsd_names

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

    def core_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        conf_obj = Configurator_Amari5GC(n['descr']['nsd']['nsd'][0]['id'], 1, self.get_id(), self.conf, n['vld'])
        return [conf_obj.dump()]

    def edge_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        pass

    def add_ues(self, msg: dict):
        pass

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
        vnfd = self.get_vnfd('core')[0]
        for vl in vnfd['vl']:
            if vl['vld'] == 'mgt':
                vl['ip'] = vlds["mgt"][0]['ip'] + '/24'
            if vl['vld'] == 'data':
                vl['ip'] = vlds["data"][0]['ip'] + '/24'

    def get_ip_edge(self, ns: dict) -> None:
        pass

    def _destroy(self):
        logger.info("Destroying")

        if hasattr(self, 'overlay_ipd'):
            self.overlay_ipd.release_all(self.conf['plmn'])
