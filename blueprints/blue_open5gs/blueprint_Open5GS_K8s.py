from blueprints.blue_5g_base import Blue5GBase
from blueprints import BlueprintBase
from nfvo import sol006_VNFbuilder, sol006_NSD_builder, get_kdu_services
import typing
from main import *

db = persistency.DB()
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)
# create logger
logger = create_logger('Open5GsK8s')


class Open5GsK8s(Blue5GBase):
    def __init__(self, conf: dict, id_: str, data: typing.Union[typing.Dict, None] = None) -> None:
        BlueprintBase.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
        logger.info("Creating Open5GS_K8s Blueprint")
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
            'update_core': [{
                'day0': [],
                'day2': [{'method': 'core_upXade'}],
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
        self.chart = "nfvcl_helm_repo/open5gs:0.1.5"
        if self.vim_core is None:
            raise ValueError('Vim CORE not found in the input')

    def set_core_vnfd(self, area: str, vls=None) -> None:
        vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
            'id': '{}_5gc'.format(self.get_id()),
            'name': '{}_5gc'.format(self.get_id()),
            'kdu': [{
                'name': '5gc',
                'helm-chart': 'nfvcl_helm_repo/open5gs:0.1.5',
                'interface': vls
            }]})
        self.vnfd['core'].append({'id': 'core', 'name': vnfd.get_id(), 'vl': vls})
        logger.debug(self.vnfd)

    def set_edge_vnfd(self, area: str, vls: list = None) -> None:
        pass
    # inherited from Amari5GC
    # def setVnfd(self, area: str, tac: int = 0, vls: list = None, pdu: dict = None) -> None:
    # def getVnfd(self, area: str, tac=None) -> list:

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
        """
        dnn: internet
        amf:
            mcc: 208
            mnc: 93
            tac: 7
        """
        """
        conf = {
            "amf": {
                "mcc": self.conf["plmn"][:3],
                "mnc": self.conf["plmn"][3:]
            }
        }
        if "dnn" in self.conf['config']:
            conf['dnn'] = self.conf['config']['dnn']
        """

        conf = {
            "n1_net": core_v['wan']['id'],
            "mgt_net": core_v['mgt'],
            "dnn_net": core_v['sgi'],
            "mcc": self.conf['plmn'][:3],
            "mnc": self.conf['plmn'][3:]
        }

        if core_v['tacs']:
            tai = []
            plmn_id = {
                    "mcc": self.conf['plmn'][:3],
                    "mnc": self.conf['plmn'][3:]
                }
            for t in core_v['tacs']:
                tai.append( {"plmn_id": plmn_id, "tac": t['id']}  )

            amf = { 'tai': tai }
            conf['amfconfigmap'] = { 'amf': amf }

            mme = { 'tai': tai }
            conf['mmeconfigmap'] = { 'mme': mme }

        # Add UEs subscribers
        if self.conf['config'] and self.conf['config']['subscribers']:
            subscribers = []
            for s in self.conf['config']['subscribers']:
                subscribers.append( {
                        'imsi': s['imsi'],
                        'k': s['k'],
                        'opc': s['opc']
                    } )
            conf['subscribers'] = subscribers

        # conf_str = {}
        # for key in conf:
        #conf_str = {'config_param': "!!yaml {}".format(yaml.dump(conf, default_flow_style=True))}

        kdu_configs = [{
            'vnf_id': '{}_5gc'.format(self.get_id()),
            'kdu_confs': [{'kdu_name': '5gc',
                           "k8s-namespace": str(self.get_id()).lower(),
                           "additionalParams": conf}]
        }]
        logger.info('core kdu_configs: {}'.format(kdu_configs))
        n_obj = sol006_NSD_builder(self.get_vnfd('core'), core_v, param, vim_net_mapping, knf_configs=kdu_configs)
        nsd_item = n_obj.get_nsd()
        nsd_item['vld'] = vim_net_mapping
        self.nsd_.append(nsd_item)
        return param['name']

    def edge_nsd(self, area: dict, vim_name: str) -> typing.List[str]:
        pass

    def core_day2_conf(self, arg: dict, nsd_item: dict) -> typing.List[str]:
        pass

    def edge_day2_conf(self, arg: dict, nsd_item: dict) -> typing.List[str]:
        pass

    def core_upXade(self, msg: dict) ->list:
        ns_core = next((item for item in self.nsd_ if item['type'] == 'core'), None)
        if ns_core is None:
            raise ValueError('core NSD not found')
        return self.kdu_upgrade(ns_core.nsd_id, msg['config'], nsi_id=ns_core['nsi_id'])

    def kdu_upgrade(self, nsd_id: str, conf_params: dict, vnf_id="1", kdu_name="5gc", nsi_id=None):
        if 'kdu_model' not in conf_params:
            conf_params['kdu_model'] = self.chart

        self.pending_updates = conf_params
        res = [
            {
                'ns-name': nsd_id,
                'primitive_data': {
                    'member-vnf-index': vnf_id,
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

    def add_slice_conf(self, msg: dict) -> list:
        pass

    def del_slice_conf(self, msg: dict) -> list:
        pass

    def add_ues(self, msg: dict):
        pass

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

    def get_ip_edge(self, n) -> None:
        pass

    def _destroy(self):
        pass