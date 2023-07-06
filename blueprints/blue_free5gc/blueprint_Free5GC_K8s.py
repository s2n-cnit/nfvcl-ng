import ipaddress
from typing import Union, Dict
from blueprints import BlueprintBase
from blueprints.blue_5g_base import Blue5GBase
from .models import *
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
    imageName = "free5gc_v3.2.0"

    @classmethod
    def rest_create(cls, msg: Free5gck8sBlueCreateModel):
        return cls.api_day0_function(msg)

    @classmethod
    def rest_add_tac(cls, msg: Free5gck8sTacModel, blue_id: str):
        msg_dict = msg.dict()
        msg_dict["operation"] = "add_tac"
        msg = Free5gck8sTacModel.parse_obj(msg_dict)
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def rest_del_tac(cls, msg: Free5gck8sTacModel, blue_id: str):
        msg_dict = msg.dict()
        msg_dict["operation"] = "del_tac"
        msg = Free5gck8sTacModel.parse_obj(msg_dict)
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def rest_add_slice(cls, msg: Free5gck8sSliceModel, blue_id: str):
        msg_dict = msg.dict()
        msg_dict["operation"] = "add_slice"
        msg = Free5gck8sSliceModel.parse_obj(msg_dict)
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def rest_del_slice(cls, msg: Free5gck8sSliceModel, blue_id: str):
        msg_dict = msg.dict()
        msg_dict["operation"] = "del_slice"
        msg = Free5gck8sSliceModel.parse_obj(msg_dict)
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def rest_add_subscriber(cls, msg: Free5gck8sSubscriberModel, blue_id: str):
        msg_dict = msg.dict()
        msg_dict["operation"] = "add_ues"
        msg = Free5gck8sSubscriberModel.parse_obj(msg_dict)
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def rest_del_subscriber(cls, msg: Free5gck8sSubscriberModel, blue_id: str):
        msg_dict = msg.dict()
        msg_dict["operation"] = "del_ues"
        msg = Free5gck8sSubscriberModel.parse_obj(msg_dict)
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def day2_methods(cls):
        cls.api_router.add_api_route(path="/{blue_id}/add_tac", endpoint=cls.rest_add_tac, methods=["PUT"],
                                     description=ADD_TAC_DESCRIPTION, summary=ADD_TAC_DESCRIPTION)
        cls.api_router.add_api_route(path="/{blue_id}/del_tac", endpoint=cls.rest_del_tac, methods=["PUT"],
                                     description=DEL_TAC_DESCRIPTION, summary=DEL_TAC_DESCRIPTION)
        cls.api_router.add_api_route(path="/{blue_id}/add_slice", endpoint=cls.rest_add_slice, methods=["PUT"],
                                     description=ADD_SLICE_DESCRIPTION, summary=ADD_SLICE_DESCRIPTION)
        cls.api_router.add_api_route(path="/{blue_id}/del_slice", endpoint=cls.rest_del_slice, methods=["PUT"],
                                     description=DEL_SLICE_DESCRIPTION, summary=DEL_SLICE_DESCRIPTION)
        cls.api_router.add_api_route(path="/{blue_id}/add_subscriber", endpoint=cls.rest_add_subscriber, methods=["PUT"],
                                     description=ADD_SUBSCRIBER_DESCRIPTION, summary=ADD_SUBSCRIBER_DESCRIPTION)
        cls.api_router.add_api_route(path="/{blue_id}/del_subscriber", endpoint=cls.rest_del_subscriber, methods=["PUT"],
                                     description=DEL_SUBSCRIBER_DESCRIPTION, summary=DEL_SUBSCRIBER_DESCRIPTION)
        pass

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None) -> None:
        BlueprintBase.__init__(self, conf, id_, data=data, db=db, nbiutil=nbiUtil)
        logger.info("Creating \"Free5GC_K8s\" Blueprint")
        self.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [{'method': 'init_day2_conf'}, {'method': 'add_ues'}],
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
        if "core" not in self.vnfd or "area" not in self.vnfd:
            self.vnfd = {'core': [], 'area': []}
        if "running_free5gc_configuration" not in self.conf:
            self.conf["running_free5gc_configuration"] = free5GC_default_config.default_config
        self.userManager = Configurator_Free5GC_User(self.conf)
        self.coreManager = Configurator_Free5GC_Core(self.conf["running_free5gc_configuration"], self.conf)
        # "msg" is used if day0 modified the msg and day2 need to use the modified version of the message
        # It is a dict where every node is in the form {"operation": "message"}, ex: {"add_slice": "...message..."}
        self.msg = dict()

    # def dropConfig(self, conf1: dict, conf2: dict):
    #     """
    #     Drop "conf2" from "conf1"
    #     @param conf1:
    #     @param conf2:
    #     @return:
    #     """
    #     if "config" in conf1 and "config" in conf2:
    #         if "sliceProfiles" in conf1["config"] and "sliceProfiles" in conf2["config"]:
    #             sliceProfiles1 = conf1["config"]["sliceProfiles"]
    #             sliceProfiles2 = conf2["config"]["sliceProfiles"]
    #             for slice2 in sliceProfiles2:
    #                 sliceToRemove = next((slice1 for index, slice1 in enumerate(sliceProfiles1)
    #                     if slice1["sliceId"] == slice2["sliceId"] and slice1["sliceType"] == slice2["sliceType"]), None)
    #                 if sliceToRemove:
    #                     sliceProfiles1.remove(sliceToRemove)
    #         if "subscribers" in conf1["config"] and "subscribers" in conf2["config"]:
    #             subscribers1 = conf1["config"]["subscribers"]
    #             subscribers2 = conf2["config"]["subscribers"]
    #             for sub2 in subscribers2:
    #                 subToRemove = next((sub1 for index, sub1 in enumerate(subscribers1)
    #                                     if sub1["imsi"] == sub2["imsi"]), None)
    #                 if subToRemove:
    #                     subscribers1.remove(subToRemove)
    #     if "areas" in conf1 and "areas" in conf2:
    #         for area2 in conf2:
    #             areaToRemove = next((item for index, item in enumerate(conf1["areas"])
    #                                  if item["id"] == area2["id"]), None)
    #             if areaToRemove:
    #                 conf1["areas"].remove(areaToRemove)

    def dropTacConfig(self, conf1: dict, conf2: dict):
        """
        Drop tac config "conf2" from "conf1"
        @param conf1:
        @param conf2:
        @return:
        """
        if "areas" not in conf1:
            logger.warn("config \"areas\" section is empty")
            return

        if "areas" in conf2:
            for area2 in conf2["areas"]:
                if "id" in area2 and "nci" in area2:
                    areaToRemove = next((area1 for area1 in conf1["areas"]
                                         if area1["id"] == area2["id"] and area1["nci"] == area2["nci"]), None)
                    if areaToRemove:
                        conf1["areas"].remove(areaToRemove)
                else:
                    logger.warn("\"id\" and/or \"nci\" are/is empty for area: {}".format(area2))

    def dropSliceConfig(self, conf1: dict, conf2: dict):
        """
        Drop slice config "conf2" from "conf1"
        @param conf1:
        @param conf2:
        @return:
        """
        if "sliceProfiles" not in conf1["config"]:
            logger.warn("\"sliceProfiles\" section in saved configuration not exists")
            return

        if "network_endpoints" not in conf1["config"]:
            logger.warn("\"network_enpoints\" section in saved configuration not exists")
            return

        if "data_nets" not in conf1["config"]["network_endpoints"]:
            logger.warn("\"data_nets\" section in saved configuration not exists")
            return

        if "network_endpoints" in conf2["config"]:
            if "data_nets" in conf2["config"]["network_endpoints"]:
                for dataNet2 in conf2["config"]["network_endpoints"]["data_nets"]:
                    dataNetToRemove = next((dataNet1 for dataNet1 in conf1["config"]["network_endpoints"]["data_nets"]
                                            if dataNet1["net_name"] == dataNet2["net_name"]), None)
                    if dataNetToRemove:
                        conf1["config"]["network_endpoints"]["data_nets"].remove(dataNetToRemove)

        if "sliceProfiles" in conf2["config"]:
            for slice2 in conf2["config"]["sliceProfiles"]:
                if "sliceId" in slice2 and "sliceType" in slice2:
                    # remove slice from "sliceProfiles" section
                    sliceToRemove = next((slice1 for slice1 in conf1["config"]["sliceProfiles"]
                        if slice1["sliceId"] == slice2["sliceId"] and slice1["sliceType"] == slice2["sliceType"]), None)
                    if sliceToRemove:
                        conf1["config"]["sliceProfiles"].remove(sliceToRemove)
                    # remove slice from "areas" section
                    if "areas" in conf1:
                        for area1 in conf1["areas"]:
                            slicesToSave = []
                            if "slices" in area1:
                                slicesToSave.extend(x for x in area1["slices"]
                                    if x["sliceType"] != slice2["sliceType"] or x["sliceId"] != slice2["sliceId"])
                                area1["slices"] = slicesToSave
                else:
                    logger.warn("\"sliceId\" and/or \"sliceTypw\" are/is not defined")


    def dropUeConfig(self, conf1: dict, conf2: dict):
        """
        Drop Ue config "conf2" from "conf1"
        @param conf1:
        @param conf2:
        @return:
        """
        if "subscribers" not in conf1["config"]:
            logger.warn("\"subscribers\" configuration section does not exist")
            return

        if "subscribers" in conf2["config"]:
            for ue2 in conf2["config"]["subscribers"]:
                ueToRemove = next((ue1 for ue1 in conf1["config"]["subscribers"] if ue1["imsi" == ue2["imsi"]]), None)
                if ueToRemove:
                    conf1["config"]["subscribers"].remove(ueToRemove)

    def sumConfig(self, conf1: dict, conf2: dict):
        """
        Add "conf2" to "conf1"
        @param conf1:
        @param conf2:
        @return:
        """
        if "config" not in conf1:
            if "config" in conf2:
                conf1["config"] = copy.deepcopy(conf2["config"])
        else:
            if "config" in conf2:
                config1 = conf1["config"]
                config2 = conf2["config"]
                if "network_endpoints" not in config1:
                    if "network_endpoints" in config2:
                        config1["network_endpoints"] = copy.deepcopy(config2["network_endpoints"])
                else:
                    if "network_endpoints" in config2:
                        network_endpoints1 = config1["network_endpoints"]
                        network_endpoints2 = config2["network_endpoints"]
                        if "data_nets" not in network_endpoints1 or network_endpoints1["data_nets"] is None:
                            if "data_nets" in network_endpoints2:
                                network_endpoints1["data_nets"] = copy.deepcopy(network_endpoints2["data_nets"])
                        else:
                            data_nets1 = network_endpoints1["data_nets"]
                            data_nets2 = network_endpoints2["data_nets"]
                            for data2 in data_nets2:
                                # looking for duplicate items to be removed before update
                                data1 = next((item for index, item in enumerate(data_nets1) if item["dnn"] == data2["dnn"]),
                                             None)
                                if data1:
                                    data_nets1.remove(data1)
                                data_nets1.append(copy.deepcopy(data2))
                if "sliceProfiles" not in config1:
                    if "sliceProfiles" not in config2:
                        config1["sliceProfiles"] = copy.deepcopy(config2["sliceProfiles"])
                else:
                    if "sliceProfiles" in config2:
                        sliceProfiles1 = config1["sliceProfiles"]
                        sliceProfiles2 = config2["sliceProfiles"]
                        for slice2 in sliceProfiles2:
                            slice1 = next((item for index, item in enumerate(sliceProfiles1)
                                           if item["sliceId"] == slice2["sliceId"] and item["sliceType"] == slice2["sliceType"]), None)
                            if slice1:
                                sliceProfiles1.remove(slice1)
                            sliceProfiles1.append(copy.deepcopy(slice2))
                if "subscribers" not in config1:
                    if "subscribers" in config2:
                        config1["subscribers"] = copy.deepcopy(config2["subscribers"])
                else:
                    if "subscribers" in config2:
                        subscribers1 = config1["subscribers"]
                        subscribers2 = config2["subscribers"]
                        for s2 in subscribers2:
                            s1 = next((item for index, item in enumerate(subscribers1)
                                                if item["imsi"] == s2["imsi"]), None)
                            if s1:
                                subscribers1.remove(s1)
                            subscribers1.append(copy.deepcopy(s2))
        if "areas" not in conf1:
            if "areas" in conf2:
                conf1["areas"] = copy.deepcopy(conf2["areas"])
        else:
            if "areas" in conf2:
                areas1 = conf1["areas"]
                areas2 = conf2["areas"]
                for a2 in areas2:
                    a1 = next((item for index, item in enumerate(areas1) if item["id"] == a2["id"]), None)
                    # if a1:
                    #     areas1.remove(a1)
                    # areas1.append(copy.deepcopy(a2))
                    if a1:
                        # copy a1 fields in a2 block
                        for key, value2 in a2.items():
                            if isinstance(value2, list) and key in a1:
                                a1[key].extend(value2)
                            else:
                                a1[key] = value2

                    else:
                        areas1.append(copy.deepcopy(a2))



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
        self.set_upfVnfd(area=area, vls=vls)
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

        # reset configuration
        self.coreManager.reset_core_configuration()

        self.coreManager.set_core_networking_parameters( interfaceName="ens3", subnetIP=core_subnetIP,
                                             gatewayIP=core_gatewayIP )

        self.coreManager.add_tacs_and_slices(self.conf)
        self.to_db()

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
                'name': "{}_5GC_{}".format(self.get_id(), self.conf['config']['plmn']),
                'id': "{}_5GC_{}".format(self.get_id(), self.conf['config']['plmn']),
                'type': 'core'
            }
            n_obj = sol006_NSD_builder(
                vnfd_k8s, core_v["name"], param, vim_net_mapping, knf_configs=kdu_configs
            )
            nsd_item = n_obj.get_nsd()
            nsd_item['area'] = core_area["id"]
            nsd_item['vld'] = vim_net_mapping
            self.nsd_.append(nsd_item)
            nsd_names.append(param["name"])

        if vnfd_os:
            for item in vnfd_os:
                param = {
                    'name': '{}_{}_{}'.format(self.get_id(), item["type"], self.conf['config']['plmn']),
                    'id': '{}_{}_{}'.format(self.get_id(), item["type"], self.conf['config']['plmn']),
                    'type': 'core'
                }
                n_obj = sol006_NSD_builder([item], core_v["name"], param, vim_net_mapping)
                nsd_item = n_obj.get_nsd()
                nsd_item['area'] = core_area["id"]
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
                'name': '{}_{}_{}_{}'.format(str(self.get_id()), t.upper(), str(area["id"]), str(self.conf['config']['plmn'])),
                'id': '{}_{}_{}_{}'.format(str(self.get_id()), t.upper(), str(area["id"]), str(self.conf['config']['plmn'])),
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

    def add_tac_nsd(self, model_msg) -> list:
        nsd_names = []
        msg = model_msg.dict()

        # save msg because "add_tac_nsd" modifies it and "add_tac_conf" uses the changed version.
        self.msg["add_tac"] = msg

        self.sumConfig(self.conf, msg)

        # add edge slices (msg) to the core (self.conf)
        coreArea = next((item for item in self.conf["areas"] if "core" in item and item["core"]), None)
        if coreArea:
            if "slices" not in coreArea:
                coreArea["slices"] = []
            if "areas" in msg:
                for area in msg["areas"]:
                    if "slices" in area:
                        for slice in area["slices"]:
                            if slice not in coreArea["slices"]:
                                coreArea["slices"].append(slice)
                # if msg has the core area node, change it with the coreArea (updated version)
                msgCoreArea = next((item for item in msg["areas"] if "core" in item and item["core"]), None)
                if msgCoreArea:
                    msg["areas"].remove(msgCoreArea)
                msg["areas"].append(coreArea)
        self.to_db()
        for area in msg['areas']:
            if "core" in area and area["core"]:
                # if area is core, do nothing
                pass
            else:
                vim = self.get_vim_name(area['id'])
                nsd_names.append(self.ran_nsd(area, vim))
                nsd_names.extend(self.edge_nsd(area, vim))
        return nsd_names

    def add_ext_nsd(self, msg) -> list:
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

    def bootstrap_day0(self, model_msg) -> list:
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

    def edge_day2_conf(self, model_arg: dict, nsd_item: dict) -> list:
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

    def init_day2_conf(self, msg) -> list:
        logger.info("Initializing Day2 configurations")
        res = []
        middle_res = []
        tail_res = []

        self.coreManager.day2_conf(self.conf)
        self.to_db()

        for n in self.nsd_:
            # configuration of external (ie. VM, not in k8s) 5G core modules, if exists (like "AMF", "UPF", etc)
            if n['type'] == 'core':
                # split return a list. nsd_name is something like "DEGFE_amf_00101". We need the first characters
                nsd_type = (n["descr"]["nsd"]["nsd"][0]["name"]).split("_")
                if nsd_type and isinstance(nsd_type[1], str) and nsd_type[1].lower() in edge_vnfd_type:
                    res += self.core_day2_conf(msg, n)
            elif n['type'] == 'ran':
                tail_res += self.ran_day2_conf(msg, n)
            elif n['type'] in edge_vnfd_type:
                # configuration of edge 5G core modules (like "UPFs")
                middle_res += self.edge_day2_conf(msg, n)

        # configuration of the 5G core
        msg2up = {'config': self.coreManager.getConfiguration()}
        middle_res += self.core_upXade(msg2up)

        res += middle_res + tail_res

        return res

    def add_ext_conf(self, msg) -> list:
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

    def del_tac_nsd(self, model_msg) -> list:
        msg = model_msg.dict()
        nsi_to_delete = super().del_area(msg)
        if "areas" in msg:
            for area in msg['areas']:
                for type in edge_vnfd_type:
                    nsd_i = next((index for index, item in enumerate(self.nsd_)
                                  if item['area'] == area['id'] and item['type'] == type), None)
                    if nsd_i is None:
                        #raise ValueError('nsd not found')
                        logger.error("nsd not found: area = {} - type = {}".format(area['id'], type))
                    nsi_id = self.nsd_[nsd_i]['nsi_id']
                    nsi_to_delete.append(nsi_id)
                    # the "pop" of the object is done by the LCM.
                    # LCM use nsd_, so don't remove it
                    #self.nsd_.pop(nsd_i)
                    # delete upf from "upf_nodes" list
                    upfNode = next((item for item in self.conf['config']['upf_nodes'] if item['nsi_id'] == nsi_id), None)
                    if upfNode:
                        self.conf['config']['upf_nodes'].remove(upfNode)

        # remove msg from config
        self.dropTacConfig(self.conf, msg)
        self.to_db()
        return nsi_to_delete

    def add_tac_conf(self, model_msg) -> list:
        # return res + tail_res -> in order reboot: UPFs - Free5GC core - gNBs
        res = []
        tail_res = []
        # here use the msg modified by "add_tac_nsd"
        #msg = model_msg.dict()
        msg = self.msg["add_tac"]

        # execute this function two times (first time)
        self.coreManager.day2_conf(msg)

        # add callback IP in self.conf
        if "callbackURL" in msg and msg["callbackURL"] != "":
            self.conf["callback"] = msg["callbackURL"]

        if "areas" in msg:
            # update upf core adding dnn (from dnnList) of all other upfs
            upfNodes = self.conf['config']['upf_nodes']
            coreUpfNode = next((item for item in upfNodes if item['type'] == 'core'), None)
            if coreUpfNode:
                for upfNode in upfNodes:
                    if upfNode["type"] != "core":
                        coreUpfNode["dnnList"].extend(
                            [item for item in upfNode["dnnList"] if item not in coreUpfNode["dnnList"]])
            #
            upfCoreRebootRequested = False
            upfCoreRebootDoing = False
            for n in self.nsd_:
                if n["area"] in [item["id"] for item in msg["areas"]]:
                    if n['type'] == 'core':
                        # split return a list. nsd_name is something like "DEGFE_amf_00101". We need the first characters
                        nsd_type = (n["descr"]["nsd"]["nsd"][0]["name"]).split("_")
                        if nsd_type and isinstance(nsd_type[1], str) and nsd_type[1].lower() in edge_vnfd_type:
                            res += self.core_day2_conf(msg, n)
                            upfCoreRebootDoing = True
                    elif n['type'] == 'ran':
                        # in the next "if", all gNBs are rebooted
                        #tail_res += self.ran_day2_conf(msg, n)
                        upfCoreRebootRequested = True
                    elif n['type'] in edge_vnfd_type:
                        # configuration of edge 5G core modules (like "UPFs")
                        res += self.edge_day2_conf(msg, n)
                # reboot all gNBs, because when add a "tac" to the core, the AMF module is rebooted and
                # so gNBs need to re-create the connection to the AMF
                if n['type'] == 'ran':
                    tail_res += self.ran_day2_conf(msg, n)

            if upfCoreRebootRequested and not upfCoreRebootDoing:
                coreNsds = [item for item in self.nsd_ if item["type"] == "core"]
                for n in coreNsds:
                    # split return a list. nsd_name is something like "DEGFE_amf_00101". We need the first characters
                    nsd_type = (n["descr"]["nsd"]["nsd"][0]["name"]).split("_")
                    if nsd_type and isinstance(nsd_type[1], str) and nsd_type[1].lower() in edge_vnfd_type:
                        res += self.core_day2_conf(msg,n)

        # execute this function two times (2nd time)
        self.coreManager.day2_conf(msg)
        self.coreManager.add_tacs_and_slices(msg)

        #res = self.coreManager.add_tac_conf(msg)
        self.coreManager.config_5g_core_for_reboot()
        self.to_db()
        res += self.core_upXade({'config': self.coreManager.getConfiguration()})
        res += tail_res
        return res

    def del_tac_conf(self, model_msg) -> list:
        msg = model_msg.dict()
        res = []
        # add callback IP in self.conf
        if "callbackURL" in msg and msg["callbackURL"] != "":
            self.conf["callback"] = msg["callbackURL"]
        self.coreManager.del_tac_conf(msg)
        self.coreManager.config_5g_core_for_reboot()
        self.to_db()
        res += self.core_upXade({'config': self.coreManager.getConfiguration()})
        return res

    def add_slice(self, msg_model) -> list:
        res = []
        tail_res = []

        msg = msg_model.dict()
        self.sumConfig(self.conf, msg)
        self.to_db()

        # add callback IP in self.conf
        if "callbackURL" in msg and msg["callbackURL"] != "":
            self.conf["callback"] = msg["callbackURL"]

        if "areas" in msg:
            for area in msg["areas"]:
                # Add DNN to UPF
                if "slices" in area:
                    for slice in area["slices"]:
                        # search dnnList used by the slice
                        sliceDnnListName = next((item["dnnList"] for item in self.conf["config"]["sliceProfiles"]
                                                 if item["sliceId"] == slice["sliceId"] and item["sliceType"] == item["sliceType"]), None)
                        if not sliceDnnListName:
                            raise ValueError("no slice in the setting message")
                        dnnList = self.coreManager.get_dnn_list_from_net_names(self.conf, sliceDnnListName)
                        logger.info("DNNLIST: {}".format(dnnList))
                        upfNode = next((item for item in self.conf['config']['upf_nodes'] if item["area"] == area["id"]), None)
                        logger.info("UPFNODE: {}".format(upfNode))
                        if upfNode:
                            for dnnElem in dnnList:
                                logger.info("DNNELEM: {}".format(dnnElem))
                                item = next((item for item in upfNode["dnnList"] if item["dnn"] == dnnElem["dnn"]), None)
                                logger.info("ITEM: {}".format(item))
                                if item:
                                    item["dns"] = dnnElem["dns"]
                                    item["pools"] = dnnElem["pools"]
                                else:
                                    upfNode["dnnList"].append(dnnElem)
                else:
                    logger.warn("no slice to add for area {}".format(area["id"]))
                    continue

                upfCoreRebootRequested = False
                upfCoreRebootDoing = False
                for nsd_item in self.nsd_:
                    if "area" in nsd_item and nsd_item['area'] == area["id"]:
                        if nsd_item['type'] == 'core':
                            # split return a list. nsd_name is something like "DEGFE_amf_00101". We need the first characters
                            nsd_type = (nsd_item["descr"]["nsd"]["nsd"][0]["name"]).split("_")
                            if nsd_type and isinstance(nsd_type[1], str) and nsd_type[1].lower() in edge_vnfd_type:
                                res += self.core_day2_conf(msg, nsd_item)
                                upfCoreRebootDoing = True
                        elif nsd_item['type'] in edge_vnfd_type:
                            res += self.edge_day2_conf(msg, nsd_item)
                            upfCoreRebootRequested = True
                        elif nsd_item['type'] == 'ran':
                            tail_res += self.ran_day2_conf(msg, nsd_item)

                if upfCoreRebootRequested and not upfCoreRebootDoing:
                    coreNsds = [item for item in self.nsd_ if item["type"] == "core"]
                    for n in coreNsds:
                        # split return a list. nsd_name is something like "DEGFE_amf_00101". We need the first characters
                        nsd_type = (n["descr"]["nsd"]["nsd"][0]["name"]).split("_")
                        if nsd_type and isinstance(nsd_type[1], str) and nsd_type[1].lower() in edge_vnfd_type:
                            res += self.core_day2_conf(msg, n)

        res += self.coreManager.add_slice(msg)
        self.coreManager.config_5g_core_for_reboot()
        self.to_db()
        res += tail_res + self.core_upXade({'config': self.coreManager.getConfiguration()})

        return res

    def add_ues(self, msg_model) -> list:
        logger.info("add_ues method starts ... type(msg_model) = {}".format(type(msg_model)))
        if isinstance(msg_model, dict):
            msg = msg_model
        else:
            msg = msg_model.dict()
        # add callback IP in self.conf
        if "callbackURL" in msg and msg["callbackURL"] != "":
            self.conf["callback"] = msg["callbackURL"]
        self.sumConfig(self.conf, msg)
        self.to_db()

        self.userManager.add_ues(msg)
        return []

    def del_ues(self, msg_model) -> list:
        if isinstance(msg_model, dict):
            msg = msg_model
        else:
            msg = msg_model.dict()

        # add callback IP in self.conf
        if "callbackURL" in msg and msg["callbackURL"] != "":
            self.conf["callback"] = msg["callbackURL"]

        self.userManager.del_ues(msg)

        # remove msg from config
        self.dropUeConfig(self.conf, msg)
        self.to_db()

        return []

    def del_slice(self, msg_model) -> list:
        logger.info("del_ues method starts ... type(msg_model) = {}".format(type(msg_model)))
        msg = msg_model.dict()

        # add callback IP in self.conf
        if "callbackURL" in msg and msg["callbackURL"] != "":
            self.conf["callback"] = msg["callbackURL"]

        res = []
        tail_res = []

        if "areas" in msg:
            for area in msg["areas"]:
                if "slices" in area:
                    for extSlice in area["slices"]:
                        dnnSliceList = []
                        if "dnnList" in extSlice:
                            dnnSliceList.extend(self.coreManager.get_dnn_list_from_net_names(self.conf, extSlice["dnnList"]))

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
                            upfCoreRebootRequested = False
                            upfCoreRebootDoing = False
                            for nsd_item in self.nsd_:
                                if "area" in nsd_item and nsd_item['area'] == area["id"]:
                                    if nsd_item['type'] == 'core':
                                        # split return a list. nsd_name is something like "DEGFE_amf_00101". We need the first characters
                                        nsd_type = (nsd_item["descr"]["nsd"]["nsd"][0]["name"]).split("_")
                                        if nsd_type and isinstance(nsd_type[1], str) and nsd_type[1].lower() in edge_vnfd_type:
                                            res += self.core_day2_conf(msg, nsd_item)
                                            upfCoreRebootDoing = True
                                    elif nsd_item['type'] in edge_vnfd_type:
                                        res += self.edge_day2_conf(msg, nsd_item)
                                        upfCoreRebootRequested = True
                                    elif nsd_item['type'] == 'ran':
                                        tail_res += self.ran_day2_conf(msg,nsd_item)

                            if upfCoreRebootRequested and not upfCoreRebootDoing:
                                coreNsds = [item for item in self.nsd_ if item["type"] == "core"]
                                for n in coreNsds:
                                    # split return a list. nsd_name is something like "DEGFE_amf_00101". We need the first characters
                                    nsd_type = (n["descr"]["nsd"]["nsd"][0]["name"]).split("_")
                                    if nsd_type and isinstance(nsd_type[1], str) and nsd_type[
                                        1].lower() in edge_vnfd_type:
                                        res += self.core_day2_conf(msg, n)

        self.coreManager.del_slice(msg)
        self.coreManager.config_5g_core_for_reboot()

        # remove msg from config
        self.dropSliceConfig(self.conf, msg)
        self.to_db()

        res += self.core_upXade({'config': self.coreManager.getConfiguration()}) + tail_res

        return res

    def core_upXade(self, msg) -> list:
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
                raise ValueError("get_ip: vim is None")
            area_id = next((item for item in vim['areas'] if item == ns['area']), None)
            if area_id is None:
                raise ValueError("get_ip: Area is None")

            logger.info('(EXT)Setting IP addresses for {} nsi for Area {} on VIM {}'
                        .format(ns['type'].upper(), area_id, vim['name']))

            # retrieving vlds from the vnf
            vnfd = self.getVnfd('area', area_id, ns['type'])[0]
            vld_names = [i['vld'] for i in vnfd['vl']]
            vlds = get_ns_vld_ip(ns['nsi_id'], vld_names)

            area_ip = None
            if len(vld_names) == 1:
                area_ip = vlds["mgt"][0]['ip']
                logger.info('{}(1) ip: {}'.format(ns['type'].upper(), area_ip))
            elif 'datanet' in vld_names:
                area_ip = vlds["datanet"][0]['ip']
                logger.info('{}(2) ip: {}'.format(ns['type'].upper(), area_ip))
            else:
                raise ValueError('({})mismatch in the enb interfaces'.format(ns['type']))

            if area_ip is None:
                raise ValueError("area_ip not defined")

            if '{}_nodes'.format(ns['type']) not in self.conf['config']:
                self.conf['config']['{}_nodes'.format(ns['type'])] = []
            node, nodeIndex = next(((item, index) for index, item in enumerate(self.conf["config"]["{}_nodes".format(ns["type"])])
                         if item["nsi_id"] == ns["nsi_id"]), (dict(), None))
            if nodeIndex == None:
                self.conf["config"]["{}_nodes".format(ns["type"])].append(node)
            node.update({
                'ip': area_ip,
                'nsi_id': ns['nsi_id'],
                'ns_id': ns['descr']['nsd']['nsd'][0]['id'],
                'type': ns['type'],
                'area': ns['area'] if 'area' in ns else None
            })
            logger.info("node ip: {}".format(area_ip))
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
            if vlds["data"][0]["vnfd_name"][-3:].lower() == "upf" or \
                    vlds["data"][0]["vnfd_name"][-8:].lower() == "upf_core":
                key = "upf_nodes"
            if vlds["data"][0]["vnfd_name"][-5:].lower() == "n3iwf":
                key = "n3iwf_nodes"
            if vlds["data"][0]["vnfd_name"][-3:].lower() == "smf":
                key = "smf_nodes"

            if key:
                if key not in self.conf['config']: self.conf['config'][key] = []
                # update the old element if exists
                node, nodeIndex = next(((item, index) for index, item in enumerate(self.conf["config"][key])
                                        if item["nsi_id"] == n["nsi_id"]), (dict(), None))
                if nodeIndex == None:
                    self.conf["config"][key].append(node)
                node.update({
                    'ip': vlds["data"][0]["ip"],
                    'nsi_id': n['nsi_id'],
                    'ns_id': n['descr']['nsd']['nsd'][0]['id'],
                    'type': n['type'],
                    'area': n['area'] if 'area' in n else None
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
