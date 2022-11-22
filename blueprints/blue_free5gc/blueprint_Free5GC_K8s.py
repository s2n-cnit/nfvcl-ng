import ipaddress
from typing import List, Union, Dict
from blueprints import BlueprintBase
from blueprints.blue_5g_base import Blue5GBase
from blueprints.blue_free5gc.models import Free5gck8sBlueCreateModel
from . import free5GC_default_config
from nfvo import sol006_VNFbuilder, sol006_NSD_builder, get_kdu_services, get_ns_vld_ip
from .configurators import Configurator_Free5GC, Configurator_Free5GC_User, Configurator_Free5GC_Core
import copy
from main import *

db = persistency.DB()
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)

# create logger
logger = create_logger('Free5GC_K8s')

# Free5GC modules exported as external VMs
edge_vnfd_type = ['upf']

class Free5GC_K8s(Blue5GBase):
    chartName = "nfvcl_helm_repo/free5gc:3.2.0"
    imageName = "free5gc_v3.0.7"

    @classmethod
    def rest_create(cls, msg: Free5gck8sBlueCreateModel):
        return cls.api_day0_function(msg)

    @classmethod
    def day2_methods(cls):
        # cls.api_router.add_api_route("/{blue_id}", cls.rest_scale, methods=["PUT"])
        pass

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None) -> None:
        BlueprintBase.__init__(self, conf, id_, data=data, db=db, nbiutil=nbiUtil)
        logger.info("Creating \"Free5GC_K8s\" Blueprint")
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
                'day2': [{'method': 'del_tac_conf'}],
                'dayN': [{'method': 'del_tac_nsd'}]
            }],
            'add_ues': [{
                'day0': [],
                'day2': [{'method': 'add_ues'}],
                'dayN': []
            }],
            'del_ues': [{
                'day0': [],
                'day2': [{'method': 'del_ues'}],
                'dayN': []
            }],
            'add_slice': [{
                'day0': [],
                'day2': [ {'method': 'add_slice'}],
                'dayN': []
            }],
            'del_slice': [{
                'day0': [],
                'day2': [{'method': 'del_slice'}],
                'dayN': []
            }],
            'update_core': [{
                'day0': [],
                'day2': [{'method': 'core_upXade'}],
                'dayN': []
            }],
            'add_ext': [{
                'day0': [{'method': 'add_ext_nsd'}],
                'day2': [{'method': 'add_ext_conf'}],
                'dayN': []
            }],
            'del_ext': [{
                'day0': [],
                'day2': [],
                'dayN': [{'method': 'del_ext_conf'}]
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
        self.vnfd = {'core': [], 'area': []}
        self.userManager = Configurator_Free5GC_User()
        self.coreManager = Configurator_Free5GC_Core(copy.deepcopy(free5GC_default_config.default_config))

    def set_baseCoreVnfd(self, vls) -> None:
        if not vls:
            raise ValueError("vls in None")
        vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
            'id': '{}_5gc'.format(self.get_id()),
            'name': '{}_5gc'.format(self.get_id()),
            'kdu': [{
                'name': '5gc',
                'helm-chart': self.chartName,
                'interface': vls
            }]})
        self.vnfd['core'].append({'id': 'core', 'name': vnfd.get_id(), 'vl': vls})

    def set_upfVnfd(self, area: str, vls=None, area_id: int = -1) -> None:
        interfaces = None
        list_ = None
        if not area:
            raise ValueError("area cannot be none")
        elif area == "core" and vls:
            interfaces = vls
        elif area == "area" and area_id >= 0:
            vim_mng = self.conf["config"]["network_endpoints"]["mgt"]
            if not vim_mng:
                raise ValueError("area = {} has not a valid vim mng network".format(area_id))
            interfaces = [
                {"vim_net": vim_mng, "vld": "mgt", "name": "ens3", "mgt": True}
            ]
            areaObj = next((item for item in self.vnfd['area'] if item['area'] == area_id), None)
            if not areaObj:
                areaObj = {'area': area_id, 'vnfd': []}
                self.vnfd['area'].append(areaObj)
            list_ = areaObj['vnfd']
        else:
            raise ValueError("area = {} is UNKNOWN".format(area))

        if not interfaces:
            raise ValueError("interfaces value cannot be none")

        if list_:
            # area
            vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
                'username': 'root',
                'password': 'root',
                'id': self.get_id() + '_free5gc_upf_' + str(area_id),
                'name': self.get_id() + '_free5gc_upf_' + str(area_id),
                'vdu': [{
                    'count': 1,
                    'id': 'VM',
                    'image': self.imageName,
                    'vm-flavor': {'memory-mb': '4096', 'storage-gb': '8', 'vcpu-count': '2'},
                    'interface': interfaces,
                    'vim-monitoring': True
                }]}, charm_name='helmflexvnfm')

            list_.append({'id': 'upf', 'name': vnfd.get_id(), 'vl': interfaces, 'type': 'upf'})
        else :
            # core
            vnfd = sol006_VNFbuilder(self.nbiutil, self.db, {
                'username': 'root',
                'password': 'root',
                'id': self.get_id() + '_free5gc_upf_core',
                'name': self.get_id() + '_free5gc_upf_core',
                'vdu': [{
                    'count': 1,
                    'id': 'VM',
                    'image': self.imageName,
                    'vm-flavor': {'memory-mb': '4096', 'storage-gb': '8', 'vcpu-count': '2'},
                    'interface': interfaces,
                    'vim-monitoring': True
                }]}, charm_name='helmflexvnfm')

            self.vnfd[area].append({'id': 'upf', 'name': vnfd.get_id(), 'vl': interfaces, 'type': 'upf'})
        logger.debug(self.vnfd)

    def set_core_vnfd(self, area: str, vls=None) -> None:
        if area != "core":
            raise ValueError("Area value is wrong")
        self.set_baseCoreVnfd(vls)
        logger.debug(self.vnfd)

    def set_edge_vnfd(self, area: str, area_id: int = 0) -> None:
        self.set_upfVnfd(area=area, area_id=area_id)

    def getVnfd(self, area: str, area_id: int = 0, type: str = None) -> list:
        id_list = []
        if not area:
            raise ValueError("Area cannot be None")
        elif area == "core":
            id_list = self.vnfd['core']
        elif area == "area":
            area_obj = next((item for item in self.vnfd['area'] if item['area'] == area_id), None)
            if not area_obj:
                raise ValueError("area {} not found in getting Vnfd".format(area_id))
            elif type:
                # create list with vnfd elements where "id" field is equal to "id" param
                id_list = [item for item in area_obj['vnfd'] if 'type' in item and item['type'] == type]
            else :
                id_list = [item for item in area_obj['vnfd'] if 'type' not in item]
        else:
            raise ValueError("area = {} is UNKNOWN".format(area))
        return id_list

    def core_nsd(self) -> List[str]:
        logger.info("Creating Core NSD(s)")
        core_area = next((item for item in self.conf["areas"] if "core" in item and item["core"]), None)
        if core_area is None:
            raise ValueError("Core area not specified")
        core_v = self.get_vim(core_area["id"])
        if self.conf["config"]["network_endpoints"]["wan"] in core_v["networks"]:
            core_v["wan"] = self.conf["config"]["network_endpoints"]["wan"]
        if not core_v:
            raise ValueError("Core VIM in msg doesn't exist")
        vim_net_mapping = [
            {'vld': 'data', 'vim_net': core_v["wan"], 'name': 'ens4', "mgt": True, 'k8s-cluster-net': 'data_net'}
        ]
        nsd_names = []

        self.set_core_vnfd("core", vls=vim_net_mapping)

        # set networking parameters for 5GC core running configuration files
        core_network = self.topology_get_network(core_v['wan'])
        if not core_network:
            raise ValueError("Core network {} not found".format(core_v['wan']))
        else:
            if "cidr" in core_network:
                core_subnetIP = str(ipaddress.IPv4Network(core_network["cidr"])[0])
            else:
                raise ValueError("Core network {} has not a valid CIDR")
            if "gateway_ip" in core_network:
                core_gatewayIP =  str(ipaddress.IPv4Network(core_network["gateway_ip"])[0])
            else:
                raise ValueError("Core network {} has not a valid gateway")

        self.coreManager.set_core_networking_parameters( interfaceName="ens3", subnetIP=core_subnetIP,
                                             gatewayIP=core_gatewayIP )

        # reset configuration
        self.coreManager.reset_core_configuration()

        self.coreManager.add_tacs_and_slices(self.conf)

        vnfd_ = self.getVnfd('core')
        # Kubernetes
        vnfd_k8s = []
        # OpenStack
        vnfd_os = []
        for item in vnfd_ :
            if "type" in item and item["type"] in edge_vnfd_type:
                vnfd_os.append(item)
            else:
                vnfd_k8s.append(item)

        if vnfd_k8s:
            kdu_configs = [{
                'vnf_id': '{}_5gc'.format(self.get_id()),
                'kdu_confs': [{'kdu_name': '5gc',
                               "k8s-namespace": str(self.get_id()).lower(),
                               "additionalParams": self.coreManager.getConfiguration()}]
            }]
            param = {
                'name': '5GC_' + str(self.conf['config']['plmn']) + "_" + str(self.get_id()),
                'id': '5GC_' + str(self.conf['config']['plmn']) + "_" + str(self.get_id()),
                'type': 'core'
            }
            n_obj = sol006_NSD_builder(
                vnfd_k8s, core_v["name"], param, vim_net_mapping, knf_configs=kdu_configs
            )
            nsd_item = n_obj.get_nsd()
            nsd_item['vld'] = vim_net_mapping
            self.nsd_.append(nsd_item)
            nsd_names.append(param["name"])

        if vnfd_os:
            for item in vnfd_os:
                param = {
                    'name': str(item["id"]) + '_' + str(self.conf['config']['plmn']) + "_" + str(self.get_id()),
                    'id': str(item["id"]) + '_' + str(self.conf['config']['plmn']) + "_" + str(self.get_id()),
                    'type': 'core'
                }
                n_obj = sol006_NSD_builder([item], core_v["name"], param, vim_net_mapping)
                nsd_item = n_obj.get_nsd()
                nsd_item['vld'] = vim_net_mapping
                self.nsd_.append(nsd_item)
                nsd_names.append(param["name"])

        return nsd_names

    # TODO: ask: why vim_name if there is area?
    def edge_nsd(self, area: dict, vim_name: str) -> List[str]:
        vim = self.get_vim(area["id"])
        if vim is None:
            raise ValueError("Area {} has not a valid VIM".format(area["id"]))
        logger.info("Creating EDGE NSD(s) for area {} on vim {}".format(area["id"], vim["name"]))
        param_name_list = []

        self.set_edge_vnfd('area', area["id"])

        vim_mgt = self.conf["config"]["network_endpoints"]["mgt"]
        vim_wan = self.conf["config"]["network_endpoints"]["wan"]

        if vim_mgt != vim_wan:
            vim_net_mapping = [
                {'vld': 'mgt', 'vim_net': vim_mgt, 'name': 'ens3', 'mgt': True},
                {'vld': 'datanet', 'vim_net': vim_wan, 'name': 'ens4', 'mgt': False}
            ]
        else:
            vim_net_mapping = [
                {'vld': 'mgt', 'vim_net': vim_wan, 'name': 'ens3', 'mgt': True}
            ]

        for t in edge_vnfd_type :
            param = {
                'name': '{}_{}_{}_{}'.format(t.upper(), str(area["id"]), str(self.conf['config']['plmn']), str(self.get_id())),
                'id': '{}_{}_{}_{}'.format(t.upper(), str(area["id"]), str(self.conf['config']['plmn']), str(self.get_id())),
                'type': '{}'.format(t)
            }
            edge_vnfd = self.getVnfd('area', area["id"], t)
            if not edge_vnfd:
                continue
            n_obj = sol006_NSD_builder(edge_vnfd, vim["name"], param, vim_net_mapping)
            nsd_item = n_obj.get_nsd()
            nsd_item['area'] = area["id"]
            nsd_item['vld'] = vim_net_mapping
            self.nsd_.append(nsd_item)
            param_name_list.append(param['name'])
        return param_name_list

    def add_ext_nsd(self, msg: dict) -> list:
        """
        Add external UPF(s) (not core) to the system
        For every TAC in the configuration message (in VIMs -> tacs) add a UPF (execution of "edge_nsd" function)
        :param msg: configuration message
        :return: list of nsd to create
        """
        nsd_names = []
        if 'areas' in msg:
            for area in msg['areas']:
                nsd_n = self.edge_nsd(area, self.get_vim_name(area["id"]))
                try:
                    nsd_names.extend(nsd_n)
                except TypeError:
                    nsd_names.append(nsd_n)
        return nsd_names

    def bootstrap_day0(self, msg) -> list:
        return self.nsd()

    def core_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        """
        Used only to configure 5GC modules OpenStack VM (at the moment of this comment, it is only "UPF")
        :param arg:
        :param nsd_item:
        :return:
        """
        logger.info("Initializing Core Day2 configurations")
        res = []

        conf_data = {
            'plmn': str(self.conf['config']['plmn']),
            'upf_nodes': self.conf['config']['upf_nodes']
        }

        config = Configurator_Free5GC(
            nsd_item['descr']['nsd']['nsd'][0]['id'],
            1,
            self.get_id(),
            conf_data
        )

        res += config.dump()
        logger.info("Module configuration built for core ")

        return res

    def edge_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        logger.info("Initializing Edge Day2 configurations")
        res = []

        conf_data = {
            'plmn': str(self.conf['config']['plmn']),
            'upf_nodes': self.conf['config']['upf_nodes'],
            'tac': nsd_item['area'] # tac of the node is the area ID
        }

        config = Configurator_Free5GC(
            nsd_item['descr']['nsd']['nsd'][0]['id'],
            1,
            self.get_id(),
            conf_data
        )

        res += config.dump()
        logger.info("Configuration built for area {}".format(nsd_item['area']))

        return res

    def init_day2_conf(self, msg: dict) -> list:
        logger.info("Initializing Day2 configurations")
        res = []

        # configuration of the 5G core
        msg2up = {'config': self.coreManager.getConfiguration()}
        res += self.core_upXade(msg2up)

        for n in self.nsd_:
            # configuration of external (ie. VM, not in k8s) 5G core modules, if exists (like "AMF", "UPF", etc)
            if n['type'] == 'core':
                # split return a list. nsd_name is something like "amf_00101_DEGFE". We need the first characters
                nsd_type = (n["descr"]["nsd"]["nsd"][0]["name"]).split("_")
                if nsd_type and isinstance(nsd_type[0], str) and nsd_type[0].lower() in edge_vnfd_type:
                    res += self.core_day2_conf(msg, n)
            elif n['type'] == 'ran':
                res += self.ran_day2_conf(msg, n)
            elif n['type'] in edge_vnfd_type:
                # configuration of edge 5G core modules (like "UPFs")
                res += self.edge_day2_conf(msg, n)

        return res

    def add_ext_conf(self, msg: dict) -> list:
        """
        Day-2 for added external UPF
        :param msg:
        :return:
        """
        res = []
        if 'areas' in msg:
            for area in msg['areas']:
                nsd_list = []
                for nsd_item in self.nsd_:
                    if nsd_item['area'] == area['id'] and nsd_item['type'] in edge_vnfd_type:
                        nsd_list.append(nsd_item)
                if not nsd_list: # list is empty
                    raise ValueError('nsd for tac {} not found'.format(area['id']))
                for nsd in nsd_list:
                    vim = self.get_vim(area["id"])
                    if not vim:
                        logger.error("area {} has not a valid VIM".format(area["id"]))
                        continue
                    res += self.edge_day2_conf({'vim': vim['name'], 'tac': area['id']}, nsd)
        return res

    def del_tac_nsd(self, msg: dict) -> list:
        nsi_to_delete = super().del_area(msg)
        if "areas" in msg:
            for area in msg['areas']:
                for type in edge_vnfd_type:
                    nsd_i = next((index for index, item in enumerate(self.nsd_)
                                  if item['area'] == area['id'] and item['type'] == type), None)
                    if nsd_i is None:
                        raise ValueError('nsd not found')
                    nsi_to_delete.append(self.nsd_[nsd_i]['nsi_id'])
                    self.nsd_.pop(nsd_i)
        return nsi_to_delete

    def add_tac_conf(self, msg: dict) -> list:
        res = self.coreManager.add_tac_conf(msg)
        self.coreManager.config_5g_core_for_reboot()
        res += self.core_upXade({'config': self.coreManager.getConfiguration()})
        return res

    def del_tac_conf(self, msg: dict) -> list:
        res = self.coreManager.del_tac_conf(msg)
        self.coreManager.config_5g_core_for_reboot()
        res += self.core_upXade({'config': self.coreManager.getConfiguration()})
        return res

    def add_slice(self, msg: dict) -> list:
        res = []
        tail_res = []

        # add callback IP in self.conf
        if "callback" in msg:
            self.conf["callback"] = msg["callback"]

        if "areas" in msg:
            for area in msg["areas"]:
                # Add DNN to UPF
                for nsd_item in self.nsd_:
                    if "area" in nsd_item and nsd_item['area'] == area["id"]:
                        if nsd_item['type'] in edge_vnfd_type:
                            conf_data = {
                                'plmn': str(self.conf['config']['plmn']),
                                'upf_nodes': self.conf['config']['upf_nodes'],
                                'tac': area["id"] # tac of the node
                            }

                            config = Configurator_Free5GC(
                                nsd_item['descr']['nsd']['nsd'][0]['id'],
                                1,
                                self.get_id(),
                                conf_data
                            )

                            res += config.dump()
                        elif nsd_item['type'] == 'ran':
                            tail_res += self.ran_day2_conf(msg, nsd_item)

                # self.config_5g_core_for_reboot()
                # msg2up = {'config': self.running_free5gc_conf}
                # res += tail_res + self.core_upXade(msg2up)

        res += self.coreManager.add_slice(msg)
        self.coreManager.config_5g_core_for_reboot()
        res += tail_res + self.core_upXade({'config': self.coreManager.getConfiguration()})

        return res

    def add_ues(self, msg: dict) -> list:
        self.userManager.add_ues(msg)
        return []

    def del_ues(self, msg: dict) -> list:
        self.userManager.del_ues(msg)
        return []

    def del_slice(self, msg: dict) -> list:
        res = []
        tail_res = []

        # add callback IP in self.conf
        if "callback" in msg:
            self.conf["callback"] = msg["callback"]

        if "areas" in msg:
            for area in msg["areas"]:
                if "slices" in area:
                    for extSlice in area["slices"]:
                        dnnSliceList = []
                        if "dnnList" in extSlice:
                            for dnn in extSlice["dnnList"]:
                                dnnSliceList.append(dnn)

                        # remove DNNs to upf configuration
                        removingDnnList = []
                        if len(dnnSliceList) != 0:
                            for upf in self.conf["config"]["upf_nodes"]:
                                if upf["tac"] == area["id"]:
                                    if "dnnList" in upf:
                                        for dnnIndex, dnnElem in enumerate(upf["dnnList"]):
                                            if dnnElem in dnnSliceList:
                                                removingDnnList.append(dnnElem)
                                                upf["dnnList"].pop(dnnIndex)

                        if len(removingDnnList) != 0:
                            for nsd_item in self.nsd_:
                                if "area" in nsd_item and nsd_item['area'] == area["id"]:
                                    if nsd_item['type'] in edge_vnfd_type:
                                        conf_data = {
                                            'plmn': str(self.conf['config']['plmn']),
                                            'upf_nodes': self.conf['config']['upf_nodes'],
                                            'tac': area["id"],  # tac of the node
                                            'removingDnnList': removingDnnList
                                        }

                                        config = Configurator_Free5GC(
                                            nsd_item['descr']['nsd']['nsd'][0]['id'],
                                            1,
                                            self.get_id(),
                                            conf_data
                                        )

                                        res += config.dump()

                                    elif nsd_item['type'] == 'ran':
                                        tail_res += self.ran_day2_conf(msg,nsd_item)

        self.coreManager.del_slice(msg)
        self.coreManager.config_5g_core_for_reboot()
        res += self.core_upXade({'config': self.coreManager.getConfiguration()}) + tail_res

        return res

    def core_upXade(self, msg: dict) -> list:
        ns_core = next((item for item in self.nsd_ if item['type'] == 'core'), None)
        if ns_core is None:
            raise ValueError('core NSD not found')
        return self.kdu_upgrade(ns_core['descr']['nsd']['nsd'][0]['name'], msg['config'], nsi_id=ns_core['nsi_id'])

    def kdu_upgrade(self, nsd_name: str, conf_params: dict, vnf_id="1", kdu_name="5gc", nsi_id=None):
        if 'kdu_model' not in conf_params:
            conf_params['kdu_model'] = self.chartName

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

        return res

    def get_ip(self) -> None:
        logger.info('Getting IP addresses of VNFIs (ext version)')
        for n in self.nsd_:
            if n['type'] in edge_vnfd_type:
                self.get_ip_edge(n)
        super().get_ip()

    def get_ip_edge(self, ns: dict) -> None:
        try:
            vim = next((item for item in self.get_vims() if item['name'] == ns['vim']), None)
            if vim is None:
                raise ValueError("get_ip vim is None")
            area = next((item for item in vim['areas'] if item['id'] == ns['area']), None)
            if area is None:
                raise ValueError("get_ip tac is None")

            logger.info('(EXT)Setting IP addresses for {} nsi for Area {} on VIM {}'
                        .format(ns['type'].upper(), area["id"], vim['name']))

            # retrieving vlds from the vnf
            vnfd = self.getVnfd('area', area["id"], ns['type'])[0]
            vld_names = [i['vld'] for i in vnfd['vl']]
            vlds = get_ns_vld_ip(ns['nsi_id'], vld_names)

            if len(vld_names) == 1:
                area['{}_ip'.format(ns['type'])] = vlds["mgt"][0]['ip']
                logger.info('{}(1) ip: {}'.format(ns['type'].upper(), area['{}_ip'.format(ns['type'])]))
            elif 'datanet' in vld_names:
                area['{}_ip'.format(ns['type'])] = vlds["datanet"][0]['ip']
                logger.info('{}(2) ip: {}'.format(ns['type'].upper(), area['{}_ip'.format(ns['type'])]))
            else:
                raise ValueError('({})mismatch in the enb interfaces'.format(ns['type']))

            if '{}_nodes'.format(ns['type']) not in self.conf['config']:
                self.conf['config']['{}_nodes'.format(ns['type'])] = []
            self.conf['config']['{}_nodes'.format(ns['type'])].append({
                'ip': area['{}_ip'.format(ns['type'])],
                'nsi_id': ns['nsi_id'],
                'ns_id': ns['descr']['nsd']['nsd'][0]['id'],
                'type': ns['type'],
                'area': ns['area'] if 'area' in ns else None
            })
            logger.info("node ip: {}".format(area['{}_ip'.format(ns['type'])]))
            logger.info("nodes: {}".format(self.conf['config']['{}_nodes'.format(ns['type'])]))
        except Exception as e:
            logger.error("({})Exception in getting IP addresses from EDGE nsi: {}"
                         .format(ns['type'].upper(), str(e)))
            raise ValueError(str(e))

    def get_ip_core(self, n) -> None:
        """
        Set IP for 5G core k8s services (AMF, SMF, etc)
        """
        logger.debug('get_ip_core')
        vlds = get_ns_vld_ip(n['nsi_id'], ["data"])
        key = None
        if "data" in vlds and len(vlds["data"]) and "ip" in vlds["data"][0]:
            if vlds["data"][0]["vnfd_name"][-3:].lower() == "amf":
                key = "amf_nodes"
                # save IP for ueransim nb
                if "config" not in self.conf:
                    self.conf['config'] = {}
                self.conf['config']['amf_ip'] = vlds["data"][0]["ip"]
            if vlds["data"][0]["vnfd_name"][-3:].lower() == "upf":
                key = "upf_nodes"
            if vlds["data"][0]["vnfd_name"][-5:].lower() == "n3iwf":
                key = "n3iwf_nodes"
            if vlds["data"][0]["vnfd_name"][-3:].lower() == "smf":
                key = "smf_nodes"

            if key:
                if key not in self.conf['config']: self.conf['config'][key] = []
                self.conf['config'][key].append({
                    'ip': vlds["data"][0]["ip"],
                    'nsi_id': n['nsi_id'],
                    'ns_id': n['descr']['nsd']['nsd'][0]['id'],
                    'type': n['type'],
                    'tac': n['area'] if 'area' in n else None
                })

        # TODO: expects more than one module for services
        try:
           kdu_services = get_kdu_services(n['nsi_id'], '5gc')
           for service in kdu_services:
               if service['type'] == 'LoadBalancer':
                   if service['name'][:3] == "nrf":
                       self.conf['config']['nrf_ip'] = service['external_ip'][0]
                   if service['name'][:4] == "ausf":
                       self.conf['config']['ausf_ip'] = service['external_ip'][0]
                   if service['name'][:4] == "nssf":
                       self.conf['config']['nssf_ip'] = service['external_ip'][0]
                   if service['name'][:3] == "udm":
                       self.conf['config']['udm_ip'] = service['external_ip'][0]
                   if service['name'][:3] == "udr":
                       self.conf['config']['udr_ip'] = service['external_ip'][0]
                   if service['name'][:3] == "pcf":
                       self.conf['config']['pcf_ip'] = service['external_ip'][0]
                   if service['name'][:3] == "amf":
                       self.conf['config']['amf_ip'] = service['external_ip'][0]
                   if service['name'][:3] == "smf":
                       self.conf['config']['smf_ip'] = service['external_ip'][0]
                   if service['name'][:3] == "n3iwf":
                       self.conf['config']['n3iwf_ip'] = service['external_ip'][0]
                   if service['name'] == "mongodb":
                       self.conf['config']['mongodb'] = service['external_ip'][0]

        except Exception as e:
            logger.info("kdu not found, managed exception: {}".format(str(e)))

    def _destroy(self):
        # TODO to be implemented
        pass
