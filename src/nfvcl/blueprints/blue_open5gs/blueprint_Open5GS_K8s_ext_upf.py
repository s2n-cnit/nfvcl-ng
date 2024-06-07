import typing
from abc import ABC
from nfvcl.blueprints.blue_5g_base.blueprint_5g_base import Blue5GBase
from nfvcl.blueprints.blueprint import BlueprintBase
from nfvcl.utils import persistency
from nfvcl.nfvo.vnf_manager import sol006_VNFbuilder
from nfvcl.nfvo.nsd_manager import sol006_NSD_builder, get_kdu_services, get_ns_vld_ip
from nfvcl.configurators import Configurator_Open5GS_UPF
from nfvcl import blueprints as open5GS_default_config
import copy
from nfvcl.utils.log import create_logger

db = persistency.DB()

# create logger
logger = create_logger('Open5GS_K8s')


class Open5GS_K8s_ext_upf(Blue5GBase, ABC):
    def __init__(self, conf: dict, id_: str, recover: bool) -> None:
        BlueprintBase.__init__(self, conf, id_)
        logger.info("Creating Open5GS_K8s Blueprint")
        self.supported_operations = {
            'init': [{
                'day0': [   {'method': 'bootstrap_day0'}    ],
                'day2': [
                            {'method': 'add_ext_upf_to_core_and_update'},
                            {'method': 'init_day2_conf'}
                        ],
                'dayN': []
            }],
            'add_tac': [{
                'day0': [   {'method': 'add_tac_nsd'}   ],
                'day2': [
                            {'method': 'add_ext_upf_to_core_and_update'},
                            {'method': 'add_tac_conf'}],
                'dayN': []
            }],
            'del_tac': [{
                'day0': [],
                'day2': [],
                'dayN': [   {'method': 'del_tac'}   ]
            }],
            'update_core': [{
                'day0': [],
                'day2': [   {'method': 'core_upXade'}   ],
                'dayN': []
            }],
            'add_ext_upf': [{
                'day0': [   {'method': 'add_ext_upf_nsd'}   ],
                'day2': [
                            {'method': 'add_ext_upf_to_core_and_update'},
                            {'method': 'add_ext_upf_conf'}
                        ],
                'dayN': []
            }],
            'del_ext_upf': [{
                'day0': [],
                'day2': [],
                'dayN': []
            }],
            'monitor': [{
                'day0': [],
                'day2': [   {'method': 'enable_prometheus'}     ],
                'dayN': []
            }],
            'log': [{
                'day0': [],
                'day2': [   {'method': 'enable_elk'}    ],
                'dayN': []
            }],
        }
        self.primitives = []
        self.vnfd = {'core': [], 'tac': [], 'upf': []}
        self.vim_core = next((item for item in self.conf['vims'] if item['core']), None)
        self.chart = "nfvcl_helm_repo/open5gs:0.1.6"
        self.running_open5gs_conf = copy.deepcopy(open5GS_default_config.default_config)
        if self.vim_core is None:
            raise ValueError('Vim CORE not found in the input')

    def set_core_vnfd(self, area: str, vls=None) -> None:
        vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
            'id': '{}_5gc'.format(self.get_id()),
            'name': '{}_5gc'.format(self.get_id()),
            'kdu': [{
                'name': '5gc',
                'helm-chart': 'nfvcl_helm_repo/open5gs:0.1.6',
                'interface': vls
            }]})
        self.vnfd['core'].append({'id': 'core', 'name': vnfd.get_id(), 'vl': vls})
        logger.debug(self.vnfd)

    def set_edgeVnfd(self, area: str, tac: int = 0, vim: dict = None) -> None:
        # Copy network from PDU
        edgeInterfaces=[
            {"vim_net": vim['mgt'], "vld": "mgt", "name": "ens3", "mgt": True},
            {"vim_net": vim['wan'], "vld": "datanet", "name": "ens4", "mgt": False},
        ]
        vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
            'username': 'root',
            'password': 'root',
            'id': self.get_id() + '_upf_' + str(tac),
            'name': self.get_id() + '_upf_' + str(tac),
            'vdu': [{
                'count': 1,
                'id': 'VM',
                'image': 'open5gs-upf',
                'vm-flavor': {'memory-mb': '4096', 'storage-gb': '8', 'vcpu-count': '2'},
                'interface': edgeInterfaces,
                'vim-monitoring': True
            }]}, charm_name='helmflexvnfm')
        self.vnfd['upf'].append({'id': 'upf', 'name': vnfd.get_id(), 'vl': edgeInterfaces})
        logger.debug(self.vnfd)

    # inherited from Amari5GC
    # def setVnfd(self, area: str, tac: int = 0, vls: list = None, pdu: dict = None) -> None:
    # def getVnfd(self, area: str, tac=None) -> list:

    def get_vnfd(self, area: str, area_id: typing.Optional[str] =None) -> list:
        if area == "upf":
            logger.debug(self.vnfd['upf'])
            return self.vnfd['upf']
        return super().get_vnfd(area, area_id)

    def core_nsd(self) -> str:
        logger.info("Creating Core NSD(s)")
        core_v = next((item for item in self.conf['vims'] if item['core']), None)
        vim_net_mapping = [
            {'vld': 'data', 'vim_net': core_v['wan']['id'], 'name': 'ens4', "mgt": True, 'k8s-cluster-net': 'data_net'}
        ]

        self.set_vnfd('core', vls=vim_net_mapping)
        param = {
            'name': '5GC_' + str(self.conf['plmn']) + "_" + str(self.get_id()),
            'id': '5GC_' + str(self.conf['plmn']) + "_" + str(self.get_id()),
            'type': 'core'
        }


        self.running_open5gs_conf['n1_net'] = core_v['wan']['id']
        self.running_open5gs_conf['mgt_net'] = core_v['mgt']
        self.running_open5gs_conf['dnn_net'] = core_v['sgi']
        self.running_open5gs_conf['mcc'] = self.conf['plmn'][:3]
        self.running_open5gs_conf['mnc'] = self.conf['plmn'][3:]

        if core_v['tacs']:
            tai = []
            ext_upf = False
            self.running_open5gs_conf['amfconfigmap']['amf']['tai'] = []
            self.running_open5gs_conf['mmeconfigmap']['mme']['tai'] = []
            plmn_id = {
                    "mcc": self.conf['plmn'][:3],
                    "mnc": self.conf['plmn'][3:]
                }
            for t in core_v['tacs']:
                self.running_open5gs_conf['amfconfigmap']['amf']['tai'].append({"plmn_id": plmn_id, "tac": t['id']})
                self.running_open5gs_conf['mmeconfigmap']['mme']['tai'].append({"plmn_id": plmn_id, "tac": t['id']})
                if 'upf_ip' in t:
                    if ext_upf == False:
                        ext_upf = True
                        self.running_open5gs_conf['smfconfigmap']['ufp']['pfcp'] = []
                    self.running_open5gs_conf['smfconfigmap']['upf']['pfcp'].append(
                        {'addr': t['upf_ip'], 'dnn': 'internet'})

        # Add UEs subscribers
        if 'config' in self.conf and 'subscribers' in self.conf['config']:
            if 'subscribers' not in self.running_open5gs_conf:
                self.running_open5gs_conf['subscribers'] = []
            for s in self.conf['config']['subscribers']:
                if s not in self.running_open5gs_conf['subscribers']:
                    self.running_open5gs_conf['subscribers'].append(s)

        # conf_str = {}
        # for key in conf:
        #conf_str = {'config_param': "!!yaml {}".format(yaml.dump(conf, default_flow_style=True))}

        self.to_db()

        kdu_configs = [{
            'vnf_id': '{}_5gc'.format(self.get_id()),
            'kdu_confs': [{'kdu_name': '5gc',
                           "k8s-namespace": str(self.get_id()).lower(),
                           "additionalParams": self.running_open5gs_conf }]
        }]
        logger.info('core kdu_configs: {}'.format(kdu_configs))
        n_obj = sol006_NSD_builder(self.get_vnfd('core'), core_v, param, vim_net_mapping, knf_configs=kdu_configs)
        nsd_item = n_obj.get_nsd()
        nsd_item['vld'] = vim_net_mapping
        self.nsd_.append(nsd_item)
        return param['name']

    def edge_nsd(self, tac: dict, vim: str) -> str:
        # NOTE: no bypass here!
        logger.info("Creating UPF NSD(s) for tac {} on vim {}".format(tac['id'], vim))

        self.set_edgeVnfd('upf', tac['id'], vim)

        param = {
            'name': 'UPF_{}_{}_{}'.format(str(tac['id']), str(self.conf['plmn']), str(self.get_id())),
            'id': 'UPF_{}_{}_{}'.format(str(tac['id']), str(self.conf['plmn']), str(self.get_id())),
            'type': 'upf'
        }
        vim_net_mapping = [
            {'vld': 'mgt', 'vim_net': vim['mgt'], "mgt": True},
            {'vld': 'datanet', 'vim_net': vim['wan']['id'], "mgt": False}
        ]
        n_obj = sol006_NSD_builder(self.get_vnfd('upf', tac['id']), vim, param, vim_net_mapping)
        nsd_item = n_obj.get_nsd()
        nsd_item['tac'] = tac['id']
        nsd_item['vld'] = vim_net_mapping
        self.nsd_.append(nsd_item)
        return param['name']

    def add_ext_upf_nsd(self, msg: dict) -> list:
        # update current blue config with new data. The "pending" status is reflected in self.nsd_ status
        #if self.check_tacs(msg):
        #    raise ValueError('TACs in msg already exist')
        #self.update_confvims(msg['vims'])
        nsd_names = []
        if 'vims' in msg:
            for v in msg['vims']:
                if 'tacs' in v:
                    for b in v['tacs']:
                        nsd_names.append(self.edge_nsd(b, v))
        return nsd_names

    def edge_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        logger.info("Initializing UPF Day2 configurations")
        logger.debug('upf_day2_conf arg: {}'.format(arg))
        res = []

        conf_data = {
           'plmn': str(self.conf['plmn']),
           'tac': nsd_item['tac']
        }

        config = Configurator_Open5GS_UPF(
            nsd_item['descr']['nsd']['nsd'][0]['id'],
            1,
            self.get_id(),
            conf_data
        )

        res += config.dump()
        logger.info("UPF configuration built for tac " + str(nsd_item['tac']))

        return res

    # inherited from Amari5GC
    # def ran_nsd(self, tac: dict, vim: dict) -> str:  # differentianting e/gNodeB?
    # def nsd(self) -> list:
    # def del_tac(self, msg: dict) -> list:
    # def add_tac_nsd(self, msg: dict) -> list:
    # def ran_day2_conf(self, arg: dict, nsd_item: dict) -> list:
    # def add_tac_conf(self, msg: dict) -> list:
    # def del_tac_conf(self, msg: dict) -> list:
    # def destroy(self):
    # def get_ip

    def init_day2_conf(self, msg: dict) -> list:
        logger.info("Initializing Day2 configurations")
        res = []
        self.to_db()
        for n in self.nsd_:
            if n['type'] == 'ran':
                # if self.pnf is False:
                #    raise ValueError("PNF not supported in this blueprint instance")
                res += self.ran_day2_conf(msg, n)
                res += self.edge_day2_conf(msg, n)
        self.to_db()
        return res

    def add_ext_upf_conf(self, msg: dict) -> list:
        res = []
        if 'vims' in msg:
            for msg_vim in msg['vims']:
                if 'tacs' in msg_vim:
                    for msg_tac in msg_vim['tacs']:
                        nsd = None
                        for nsd_item in self.nsd_:
                            if nsd_item['type'] == 'upf':
                                if nsd_item['tac'] == msg_tac['id']:
                                    nsd = nsd_item
                                    break
                        if nsd is None:
                            raise ValueError('nsd for tac {} not found'.format(msg_tac['id']))
                        res += self.edge_day2_conf({'vim': msg_vim['name'], 'tac': msg_tac['id']}, nsd)
        return res

    ## FIXME!!!!!!! erase this function!
    ## this was added to override the parent's function, in order to avoid
    ## the search for pdus in mongodb
    # def nsd(self) -> list:
    #    nsd_names = [self.core_nsd()]
    #    logger.info("NSDs created")
    #    return nsd_names

    def core_upXade(self, msg: dict) ->list:
        ns_core = next((item for item in self.nsd_ if item['type'] == 'core'), None)
        if ns_core is None:
            raise ValueError('core NSD not found')
        return self.kdu_upgrade(ns_core['descr']['nsd']['nsd'][0]['name'], msg['config'], nsi_id=ns_core['nsi_id'])

    def kdu_upgrade(self, nsd_name: str, conf_params: dict, vnf_id="1", kdu_name="5gc", nsi_id=None):
        if 'kdu_model' not in conf_params:
            conf_params['kdu_model'] = self.chart

        self.pending_updates = conf_params
        res = [
            {
                'ns-name': nsd_name,
                'primitive_data': {
                    'member_vnf_index': vnf_id,
                    'kdu_name': kdu_name,
                    'primitive': 'upgrade',
                    'primitive_params': conf_params
                }
            }
        ]
        if nsi_id is not None:
            res[0]['nsi_id'] = nsi_id
        self.config_content = {}
        """
        if hasattr(self, "action_list"):
            if isinstance(self.action_list, list):
                self.action_list.append({"action": res, "time": now.strftime("%H:%M:%S")})
        """
        # TODO check if the the following commands are needed
        if hasattr(self, "nsi_id"):
            if self.nsi_id is not None:
                for r in res:
                    r['nsi_id'] = self.nsi_id

        return res

    def add_ext_upf_to_core_and_update(self, msg: dict ) -> list:
        logger.info("Add external UPF address to Core")
        pfcp = []
        config = {}
        if 'vims' in msg:
            for v in msg['vims']:
                if 'tacs' in v:
                    for t in v['tacs']:
                        if 'upf_ip' in t:
                            pfcp.append({'addr': t['upf_ip'], 'dnn': 'internet'})
                if len(pfcp) > 0:
                    upf = {'pfcp': pfcp}
                    config['smfconfigmap'] = {'upf': upf}
        self.running_open5gs_conf.update( config )
        self.to_db()
        logger.debug("msg['config'] : {}".format( self.running_open5gs_conf ))
        return self.core_upXade( { 'config': self.running_open5gs_conf } )

    def add_slice_conf(self, msg: dict) -> list:
        pass

    def del_slice_conf(self, msg: dict) -> list:
        pass

    def get_ip(self) -> None:
        logger.info('Getting IP addresses of VNFIs (UPF version)')
        for n in self.nsd_:
            if n['type'] == 'upf':
                try:
                    vim = next((item for item in self.conf['vims'] if item['name'] == n['vim']), None)
                    if vim is None:
                        raise ValueError("get_ip vim is None")
                    tac = next((item for item in vim['tacs'] if item['id'] == n['tac']), None)
                    if tac is None:
                        raise ValueError("get_ip tac is None")

                    logger.info('(UPF)Setting IP addresses for RAN nsi for TAC {} on VIM {}'.format(tac['id'], vim['name']))

                    # retrieving vlds from the vnf
                    vnfd = self.get_vnfd('tac', tac['id'])[0]
                    vld_names = [i['vld'] for i in vnfd['vl']]
                    vlds = get_ns_vld_ip(n['nsi_id'], vld_names)

                    if len(vld_names) == 1:
                        tac['upf_ip'] = vlds["mgt"][0]['ip']
                        logger.info('UPF(1) ip: {}'.format(tac['upf_ip']))
                    elif 'data' in vld_names:
                        tac['upf_ip'] = vlds["data"][0]['ip']
                        logger.info('UPF(2) ip: {}'.format(tac['upf_ip']))
                    else:
                        raise ValueError('(UPF)mismatch in the enb interfaces')
                except Exception as e:
                    logger.error("(UPF)Exception in getting IP addresses from RAN nsi: " + str(e))
                    raise ValueError(str(e))

        # saving operation yet done in "super().get_ip()"
        #self.save_conf()

        super().get_ip()


    def get_ip_core(self, n) -> None:
        logger.debug('get_ip_core')
        kdu_services = get_kdu_services(n['nsi_id'], '5gc')
        logger.debug(kdu_services)
        for service in kdu_services:
            if service['type'] == 'LoadBalancer':
                if service['name'][:3] == "amf":
                    self.conf['config']['amf_ip'] = service['external_ip'][0]
                elif service['name'][-6:] == "mme-lb":
                    self.conf['config']['mme_ip'] = service['external_ip'][0]
                elif service['name'][-6:] == "-webui":
                    self.conf['config']['web_ip'] = service['external_ip'][0]
                elif service['name'][-4:] == "-upf":
                    self.conf['config']['upf_ip'] = service['external_ip'][0]
                elif service['name'][-5:] == "-sgwu":
                    self.conf['config']['sgwu_ip'] = service['external_ip'][0]
        logger.debug(self.conf['config'])
        """
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
        """
