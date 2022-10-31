import typing

from blueprints.blue_amari5G.blueprint_amari5G import Amari5G
from blueprints.blueprint import BlueprintBase
from utils import persistency
from nfvo.vnf_manager import sol006_VNFbuilder
from nfvo.nsd_manager import sol006_NSD_builder, get_kdu_services, get_ns_vld_ip
from utils.util import create_logger
from configurators.free5gc_configurator import Configurator_Free5GC
from pymongo import MongoClient
from bson import ObjectId
import blueprints.blue_free5gc.free5GC_default_config as free5GC_default_config
import copy
import yaml
import random

db = persistency.db()

# create logger
logger = create_logger('Free5GC_K8s')


class NoAliasDumper(yaml.SafeDumper):
    """
    Used to remove "anchors" and "aliases" from yaml file
    """
    def ignore_aliases(self, data):
        return True

class Free5GC_K8s(Amari5G):
    # Free5GC modules exported as external VMs
    edge_vnfd_type = ['upf']

    def __init__(self, conf: dict, id_: str, recover: bool) -> None:
        BlueprintBase.__init__(self, conf, id_)
        logger.info("Creating \"Free5GC_K8s\" Blueprint")
        self.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [
                    #{'method': 'add_ext_to_core_and_update'},
                    {'method': 'init_day2_conf'}
                ],
                'dayN': []
            }],
            'add_tac': [{
                'day0': [{'method': 'add_tac_nsd'}],
                'day2': [{'method': 'add_tac_conf'}],
                'dayN': []
            }],
            'del_tac': [{
                'day0': [{'method': 'del_tac_nsd'}],
                'day2': [{'method': 'del_tac_conf'}],
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
        self.vnfd = {'core': [], 'tac': []}
        self.vim_core = next((item for item in self.conf['vims'] if item['core']), None)
        self.chart = "nfvcl_helm_repo/free5gc:3.0.9"
        self.running_free5gc_conf = copy.deepcopy(free5GC_default_config.default_config)
        # default slices
        #self.defaultSliceList = [{"sd": "000001", "sst": 1}]
        self.defaultSliceList = []
        # default dnn(s)
        self.defaultDnnList = [{"dnn": "internet", "dns": { "ipv4": "8.8.8.8"}, "pools": [{ "cidr": "60.60.0.0/24"}]}]
        if self.vim_core is None:
            raise ValueError('Vim CORE not found in the input')

    def set_baseCoreVnfd(self, area: str, vls=None) -> None:
        vnfd = sol006_VNFbuilder({
            'id': '{}_5gc'.format(self.get_id()),
            'name': '{}_5gc'.format(self.get_id()),
            'kdu': [{
                'name': '5gc',
                'helm-chart': 'nfvcl_helm_repo/free5gc:3.0.9',
                'interface': vls
            }]})
        self.vnfd['core'].append({'id': 'core', 'name': vnfd.get_id(), 'vl': vls})

    def set_upfVnfd(self, area: str, vls=None, tac: int = 0, vim: dict = None) -> None:
        interfaces = None
        list_ = None
        if area == "core":
            interfaces = vls
        elif area == "tac":
            # Copy network from PDU
            interfaces = [
                #{"vim_net": vim['wan']['id'], "vld": "datanet", "name": "ens4", "mgt": False},
                {"vim_net": vim['mgt'], "vld": "mgt", "name": "ens3", "mgt": True}
            ]
            tacObj = next((item for item in self.vnfd['tac'] if item['tac'] == tac), None)
            if tacObj == None:
                tacObj = {'tac': tac, 'vnfd': []}
                self.vnfd['tac'].append(tacObj)

            list_ = tacObj['vnfd']
        else:
            raise ValueError("area = {} is UNKNOWN".format(area))

        if list_ :
            # tac
            vnfd = sol006_VNFbuilder({
                'username': 'root',
                'password': 'root',
                'id': self.get_id() + '_free5gc_upf_' + str(tac),
                'name': self.get_id() + '_free5gc_upf_' + str(tac),
                'vdu': [{
                    'count': 1,
                    'id': 'VM',
                    'image': 'free5gc_v3.0.7',
                    'vm-flavor': {'memory-mb': '4096', 'storage-gb': '8', 'vcpu-count': '2'},
                    'interface': interfaces,
                    'vim-monitoring': True
                }]}, charm_name='helmflexvnfm')

            list_.append({'id': 'upf', 'name': vnfd.get_id(), 'vl': interfaces, 'type': 'upf'})
        else :
            # core
            vnfd = sol006_VNFbuilder({
                'username': 'root',
                'password': 'root',
                'id': self.get_id() + '_free5gc_upf',
                'name': self.get_id() + '_free5gc_upf',
                'vdu': [{
                    'count': 1,
                    'id': 'VM',
                    'image': 'free5gc_v3.0.7',
                    'vm-flavor': {'memory-mb': '4096', 'storage-gb': '8', 'vcpu-count': '2'},
                    'interface': interfaces,
                    'vim-monitoring': True
                }]}, charm_name='helmflexvnfm')

            self.vnfd[area].append({'id': 'upf', 'name': vnfd.get_id(), 'vl': interfaces, 'type': 'upf'})
        logger.debug(self.vnfd)

    def set_coreVnfd(self, area: str, vls=None) -> None:
        self.set_baseCoreVnfd(area, vls)

        logger.debug(self.vnfd)

    def set_edgeVnfd(self, area: str, tac: int = 0, vim: dict = None) -> None:
        self.set_upfVnfd(area=area, tac=tac, vim=vim)

    def getVnfd(self, area: str, tac: typing.Optional[str] = None, type: str = None) -> list:
        id_list = []
        if area == "core":
            logger.debug(self.vnfd['core'])
            id_list = self.vnfd['core']
        if area == "tac":
            if tac is None:
                raise ValueError("tac is None in getVnfd")
            tac_obj = next((item for item in self.vnfd['tac'] if item['tac'] == tac), None)
            if tac_obj is None:
                raise ValueError("tac not found in getting Vnfd")
            if type:
                # create list with vnfd elements where "id" field is equal to "id" param
                id_list = [item for item in tac_obj['vnfd'] if 'type' in item and item['type'] == type]
            else :
                id_list = [item for item in tac_obj['vnfd'] if 'type' not in item]
        return id_list

    def amf_reset_configuration(self) -> None:
        # AMF reset configuration
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]["servedGuamiList"] = []
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]["supportTaiList"] = []
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]["plmnSupportList"] = []
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]["supportDnnList"] = []
        amfConfigurationBase = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configuration"] = \
            yaml.dump(amfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def amf_set_configuration(self, supportedTacList: list = None, amfId: str = None, mcc: str = None, mnc: str = None,
            snssaiList: list = None, dnnList: list = None) -> str :
        """
        Configure AMF configMap
        :param supportedTacList: [24]
        :param amfId: "cafe01"
        :param mcc: "001"
        :param mnc: "01"
        :param snssaiList: ex. [{"sst": 1, "sd": "000001"}]
        :param dnnList: ex. [{"dnn": "internet", "dns": "8.8.8.8"}]
        :return: amfId
        """
        # AMF configuration
        if mcc == None : mcc = self.conf['plmn'][:3]
        if mnc == None : mnc = self.conf['plmn'][3:]
        #if amfId == None: amfId = str(random.choice(string.ascii_lowercase) for i in range(6))
        if amfId == None: amfId = "{0:06x}".format(random.randrange(0x000000, 0xFFFFFF))
        guamiItem = {"plmnId": {"mcc": mcc, "mnc": mnc}, "amfId": amfId}
        servedGuamiList = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"] \
            ["servedGuamiList"]
        if guamiItem not in servedGuamiList:
                    servedGuamiList.append(guamiItem)

        supportTaiList = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"] \
                ["supportTaiList"]

        if supportedTacList != None:
            for tac in supportedTacList:
                supportTaiItem = {"plmnId": {"mcc": mcc, "mnc": mnc}, "tac": tac}
                if supportTaiItem not in supportTaiList:
                    supportTaiList.append(supportTaiItem)

        plmnSupportList = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"] \
            ["plmnSupportList"]
        plmnId = {"mcc": mcc, "mnc": mnc}
        plmnFound = False
        for plmnIdSupportItem in plmnSupportList:
            if plmnIdSupportItem["plmnId"] == plmnId:
                plmnFound = True
                if snssaiList != None:
                    for snssaiItem in snssaiList:
                        if snssaiItem not in plmnIdSupportItem["snssaiList"]:
                            plmnIdSupportItem["snssaiList"].append(snssaiItem)
                break
        if plmnFound == False:
            plmnIdSupportItem = {"plmnId": plmnId, "snssaiList": []}
            if snssaiList != None:
                for snssaiItem in snssaiList:
                    if snssaiItem not in plmnIdSupportItem["snssaiList"]:
                        plmnIdSupportItem["snssaiList"].append(snssaiItem)
            plmnSupportList.append(plmnIdSupportItem)

        supportDnnList = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"] \
            ["supportDnnList"]
        if dnnList != None:
            for dnnItem in dnnList:
                if dnnItem["dnn"] not in supportDnnList:
                    supportDnnList.append(dnnItem["dnn"])

        amfConfigurationBase = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]
        logger.info("AMFCONFIGURATIONBASE")
        logger.info("{}".format(amfConfigurationBase))
        logger.info("**********************************")
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configuration"] = \
            yaml.dump(amfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        return amfId

    def amf_unset_configuration(self, snssaiList: list = None, dnnList: list = None,
                                mcc: str = None, mnc: str = None) -> None:
        if mcc == None : mcc = self.conf['plmn'][:3]
        if mnc == None : mnc = self.conf['plmn'][3:]
        plmnId = {"mcc": mcc, "mnc": mnc}

        if snssaiList != None:
            plmnSupportList = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"] \
                ["plmnSupportList"]
            for plmnIdSupportIndex, plmnIdSupportItem in enumerate(plmnSupportList):
                if plmnIdSupportItem["plmnId"] == plmnId:
                    for snssaiIndex, snssaiItem in enumerate(plmnIdSupportItem["snssaiList"]):
                        if snssaiItem in snssaiList:
                            plmnIdSupportItem["snssaiList"].pop(snssaiIndex)

        if dnnList != None:
            supportDnnList = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"] \
                ["supportDnnList"]
            for dnnItem in dnnList:
                if dnnItem["dnn"] in supportDnnList:
                    index = supportDnnList.index(dnnItem["dnn"])
                    supportDnnList.pop(index)

        amfConfigurationBase = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configuration"] = \
            yaml.dump(amfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def ausf_reset_configuration(self) -> None:
        # AUSF reset
        self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"]["plmnSupportList"] = []
        ausfConfigurationBase = self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configuration"] = \
            yaml.dump(ausfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def ausf_set_configuration(self, mcc: str = None, mnc: str = None) -> None :
        # AUSF configuration
        if mcc == None: mcc = self.conf['plmn'][:3]
        if mnc == None: mnc = self.conf['plmn'][3:]
        plmnSupportItem = {"mcc": mcc, "mnc": mnc}
        plmnSupportList = self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"] \
            ["plmnSupportList"]
        if plmnSupportItem not in plmnSupportList:
            plmnSupportList.append(plmnSupportItem)
        ausfConfigurationBase = self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configuration"] = \
            yaml.dump(ausfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def n3iwf_reset_configuration(self) -> None:
        # N3IWF configuration
        self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configurationBase"]["N3IWFInformation"] = \
            {"GlobalN3IWFID": {"PLMNID": {"MCC": "", "MNC": ""}, "N3IWFID": ""}, "Name": "",
             "SupportedTAList": []}
        n3iwfConfigurationBase = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"][
            "configurationBase"]
        self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configuration"] = \
            yaml.dump(n3iwfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def n3iwf_set_configuration(self, mcc: str = None, mnc: str = None, name: str = None, tac: int = -1,
            sliceSupportList: list = None, n3iwfId: int = -1) -> str:
        # N3IWF configuration
        if mcc == None: mcc = self.conf['plmn'][:3]
        if mnc == None: mnc = self.conf['plmn'][3:]
        #if name == None: name = str(random.choice(string.ascii_lowercase) for i in range(6))
        if name == None: name = "{0:06x}".format(random.randrange(0x000000, 0xFFFFFF))
        if n3iwfId == -1: n3iwfId = random.randint(1,9999)

        n3iwfInformation = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configurationBase"] \
            ["N3IWFInformation"]
        n3iwfInformation["GlobalN3IWFID"]["N3IWFID"] = n3iwfId
        n3iwfInformation["GlobalN3IWFID"]["PLMNID"]["MCC"] = mcc
        n3iwfInformation["GlobalN3IWFID"]["PLMNID"]["MNC"] = mnc
        n3iwfInformation["Name"] = name

        if tac != -1:
            taFound = False
            TAC = "{:x}".format(tac)
            for supportedTAItem in n3iwfInformation["SupportedTAList"]:
                if supportedTAItem["TAC"] == TAC:
                    taFound = True
                    plmnIdFound = False
                    for item in supportedTAItem["BroadcastPLMNList"]:
                        if item["PLMNID"] == {"MCC": mcc, "MNC": mnc}:
                            plmnIdFound = True
                            if sliceSupportList != None:
                                for slice in sliceSupportList:
                                    sl = {"SNSSAI": {"SD": slice["sd"], "SST": slice["sst"]}}
                                    if sl not in item["TAISliceSupportList"]:
                                        item["TAISliceSupportList"].append(sl)
                    if plmnIdFound == False:
                        TAISliceSupportList = []
                        if sliceSupportList != None:
                            for slice in sliceSupportList:
                                sl = {"SNSSAI": {"SD": slice["sd"], "SST": slice["sst"]}}
                                TAISliceSupportList.append(sl)
                            sTAItem =  [{"PLMNID": {"MCC": mcc, "MNC": mnc}, "TAC": TAC,
                                "TAISliceSupportList": TAISliceSupportList}]
                            n3iwfInformation["SupportedTAList"].append(sTAItem)
            if taFound == False:
                TAISliceSupportList = []
                if sliceSupportList != None:
                    for slice in sliceSupportList:
                        TAISliceSupportList.append({"SNSSAI": {"SD": slice["sd"], "SST": slice["sst"]}})
                    n3iwfInformation["SupportedTAList"].append({"TAC": TAC, "BroadcastPLMNList":
                        [{"PLMNID": {"MCC": mcc, "MNC": mnc},
                        "TAISliceSupportList": TAISliceSupportList}]})

        n3iwfConfigurationBase = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"][
            "configurationBase"]
        self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configuration"] = \
            yaml.dump(n3iwfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        return name

    def n3iwf_unset_configuration(self, sliceSupportList: list = None) -> None:
        if sliceSupportList != None:
            n3iwfInformation = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configurationBase"] \
                ["N3IWFInformation"]
            if "SupportedTAList" in n3iwfInformation:
                for supportedTAItem in n3iwfInformation["SupportedTAList"]:
                    if "BroadcastPLMNList" in supportedTAItem:
                        for broadcastItem in supportedTAItem["BroadcastPLMNList"]:
                            if "TAISliceSupportList" in broadcastItem:
                                for taiSliceIndex, taiSliceItem in enumerate(broadcastItem["TAISliceSupportList"]):
                                    if "SNSSAI" in taiSliceItem:
                                        slice = {"sd": taiSliceItem["SNSSAI"]["SD"], "sst": taiSliceItem["SNSSAI"]["SST"]}
                                        if slice in sliceSupportList:
                                            broadcastItem["TAISliceSupportList"].pop(taiSliceIndex)

        n3iwfConfigurationBase = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"][
            "configurationBase"]
        self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configuration"] = \
            yaml.dump(n3iwfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def nrf_reset_configuration(self) -> None:
        # NRF configuration
        self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]["DefaultPlmnId"] = {}
        nrfConfigurationBase = self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configuration"] = \
            yaml.dump(nrfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def nrf_set_configuration(self, mcc: str = None, mnc: str = None):
        # NRF configuration
        if mcc == None: mcc = self.conf['plmn'][:3]
        if mnc == None: mnc = self.conf['plmn'][3:]
        self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]["DefaultPlmnId"] = \
            {"mcc": mcc, "mnc": mnc}
        nrfConfigurationBase = self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configuration"] = \
            yaml.dump(nrfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def nssf_reset_configuration(self) -> None:
        # NSSF configuration
        mcc = self.conf['plmn'][:3]
        mnc = self.conf['plmn'][3:]
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["supportedPlmnList"] = []
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"] \
            ["supportedNssaiInPlmnList"] = []
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"] \
            ["amfList"] = []
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"] \
            ["taList"] = []
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"] \
            ["supportedNssaiInPlmnList"] = []
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"] \
            ["mappingListFromPlmn"] = []
        nssfConfigurationBase = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configuration"] = \
            yaml.dump(nssfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def nssf_set_configuration(self, mcc: str = None, mnc: str = None, operatorName: str = "CNIT", nssfName: str = None,
            sliceList: list = None, nfId: str = None, tac: int = -1) -> str:
        # NSSF configuration
        if mcc == None: mcc = self.conf['plmn'][:3]
        if mnc == None: mnc = self.conf['plmn'][3:]
        #if nssfName == None: nssfName = str(random.choice(string.ascii_lowercase) for i in range(6))
        if nssfName == None: nssfName = "{0:06x}".format(random.randrange(0x000000, 0xFFFFFF))
        #if nfId == None: nfId = str(random.choice(string.digits) for i in range(35))
        if nfId == None: nfId = "{:035d}".format(random.randrange(0x0, 0x13426172C74D822B878FE7FFFFFFFF))

        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["nssfName"] = nssfName

        supportedPlmnList = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"] \
            ["supportedPlmnList"]
        supportedPlmnItem = {"mcc": mcc, "mnc": mnc}
        if supportedPlmnItem not in supportedPlmnList:
            supportedPlmnList.append(supportedPlmnItem)

        if tac != -1:
            tai = {"plmnId": {"mcc": mcc, "mnc": mnc}, "tac": tac}

            supportedNssaiInPlmnList = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"] \
                ["configurationBase"]["supportedNssaiInPlmnList"]
            plmnId = {"mcc": mcc, "mnc": mnc}
            plmnIdFound = False
            for supportedNssaiInPlmnItem in supportedNssaiInPlmnList:
                if supportedNssaiInPlmnItem["plmnId"] == plmnId:
                    plmnIdFound = True
                    if sliceList != None:
                        for slice in sliceList:
                            if {"sd": slice["sd"], "sst": slice["sst"]} not in supportedNssaiInPlmnItem["supportedSnssaiList"]:
                                supportedNssaiInPlmnItem["supportedSnssaiList"].append(
                                        {"sd": slice["sd"], "sst": slice["sst"]})
            if plmnIdFound == False:
                supportedNssaiInPlmnList.append({"plmnId": plmnId,
                    "supportedSnssaiList": sliceList})

            amfList = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["amfList"]
            nfIdFound = False
            taiFound = False
            for amfItem in amfList:
                supportedNssaiAvailabilityData = amfItem["supportedNssaiAvailabilityData"]
                for item in supportedNssaiAvailabilityData:
                    if item["tai"] == tai:
                        taiFound = True
                        if sliceList != None:
                            for slice in sliceList:
                                if slice not in item["supportedSnssaiList"]:
                                    item["supportedSnssaiList"].append(slice)
                        break
                if amfItem["nfId"] == nfId:
                    nfIdFound = True
                    if taiFound == False:
                        supportedNssaiAvailabilityData.append(
                        {"tai": "{}".format(tai), "supportedSnssaiList": sliceList})
                        break

            if nfIdFound == False and taiFound == False:
                amfList.append({"nfId": nfId, "supportedNssaiAvailabilityData":
                    [{"tai": tai, "supportedSnssaiList": sliceList}]})

            taiFound = False
            taList = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["taList"]
            for taItem in taList:
                if taItem["tai"] == tai:
                    taiFound = True
                    if sliceList != None:
                        for slice in sliceList:
                            if slice not in taItem["supportedSnssaiList"]:
                                taItem["supportedSnssaiList"].append(slice)
            if taiFound == False:
                taList.append(
                        {"accessType":"3GPP_ACCESS", "supportedSnssaiList": sliceList, "tai": tai})

            mappingListFromPlmn = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"] \
                ["mappingListFromPlmn"]
            homePlmnIdFound = False
            for item in mappingListFromPlmn:
                if item["homePlmnId"] == plmnId:
                    homePlmnIdFound = True
                    if sliceList != None:
                        for slice in sliceList:
                            mappingItem = {"homeSnssai": slice, "servingSnssai": slice}
                            if mappingItem not in item["mappingOfSnssai"]:
                                item["mappingOfSnssai"].append(mappingItem)
            if homePlmnIdFound == False:
                mappingOfSnssai = []
                for slice in sliceList:
                    mappingOfSnssai.append({"homeSnssai": slice, "servingSnssai": slice})
                mappingListFromPlmn.append(
                        {"homePlmnId": plmnId, "mappingOfSnssai": mappingOfSnssai,
                        "operatorName": operatorName})


        nssfConfigurationBase = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configuration"] = \
            yaml.dump(nssfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

        return nfId

    def nssf_unset_configuration(self, sliceList: list = None) -> None:

        if sliceList != None:
            supportedNssaiInPlmnList = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"] \
                ["configurationBase"]["supportedNssaiInPlmnList"]
            for supportedNssaiInPlmnItem in supportedNssaiInPlmnList:
                if "supportedSnssaiList" in supportedNssaiInPlmnItem:
                    for supportedSnssaiIndex, supportedSnssaiItem in \
                            enumerate(supportedNssaiInPlmnItem["supportedSnssaiList"]):
                        if supportedSnssaiItem in sliceList:
                            supportedNssaiInPlmnItem["supportedSnssaiList"].pop(supportedSnssaiIndex)
                            break

            amfList = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["amfList"]
            for amfItem in amfList:
                if "supportedNssaiAvailabilityData" in amfItem:
                    for supportedNssaiItem in amfItem["supportedNssaiAvailabilityData"]:
                        if "supportedSnssaiList" in supportedNssaiItem:
                            for supportedSnssaiIndex, supportedSnssaiItem \
                                    in enumerate(supportedNssaiItem["supportedSnssaiList"]):
                                if supportedSnssaiItem in sliceList:
                                    supportedNssaiItem["supportedSnssaiList"].pop(supportedSnssaiIndex)

            taList = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["taList"]
            for taItem in taList:
                if "supportedSnssaiList" in taItem:
                    for supportedSnssaiIndex, supportedSnssaiItem in enumerate(taItem["supportedSnssaiList"]):
                        if supportedSnssaiItem in sliceList:
                            taItem["supportedSnssaiList"].pop(supportedSnssaiIndex)

            mappingListFromPlmn = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]\
                ["configurationBase"]["mappingListFromPlmn"]
            for mappingListItem in mappingListFromPlmn:
                if "mappingOfSnssai" in mappingListItem:
                    for mappingOfSnssaiIndex, mappingOfSnssaiItem in enumerate(mappingListItem["mappingOfSnssai"]):
                        if "homeSnssai" in mappingOfSnssaiItem:
                            if mappingOfSnssaiItem["homeSnssai"] in sliceList:
                                mappingOfSnssaiItem.pop("homeSnssai")
                            if mappingOfSnssaiItem["servingSnssai"] in sliceList:
                                mappingOfSnssaiItem.pop("servingSnssai")
                            if "homeSnssai" not in mappingOfSnssaiItem and "servingSnssai" not in mappingOfSnssaiItem:
                                mappingListItem["mappingOfSnssai"].pop(mappingOfSnssaiIndex)


        nssfConfigurationBase = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configuration"] = \
            yaml.dump(nssfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def pcf_reset_configuration(self) -> None:
        # PCF configuration
        self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["pcfName"] = None
        pcfConfigurationBase = self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configuration"] = \
            yaml.dump(pcfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def pcf_set_configuration(self, pcfName: str = None) -> str:
        # PCF configuration
        #if pcfName == None: pcfName = str(random.choice(string.digits) for i in range(6))
        if pcfName == None: pcfName = "{:06d}".format(random.randrange(0x000000, 0xFFFFFF))
        self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["pcfName"] = pcfName
        pcfConfigurationBase = self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configuration"] = \
            yaml.dump(pcfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        return pcfName

    def smf_reset_configuration(self) -> None:
        # SMF configuration
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["smfName"] = ""
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["snssaiInfos"] = []

        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["plmnList"] = []
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"] \
            ["userplane_information"] = {"up_nodes": {}, "links": []}

        smfConfigurationBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configuration"] = \
            yaml.dump(smfConfigurationBase, explicit_start=False, default_flow_style=False)
        smfUeRoutingInfoBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfoBase"]
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfo"] = \
            yaml.dump(smfUeRoutingInfoBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def smf_set_configuration(self, mcc: str = None, mnc: str = None, smfName: str = None, dnnList: list = None,
            sliceList: list = None, links: list = None, upNodes: dict = None) -> str:
        """

        :param mcc:
        :param mnc:
        :param smfName:
        :param dnnList: es. [{"dnn": "internet", "dns": "8.8.8.8"}]
        :param sliceList: es. [{"sst": 1, "sd": "000001"}]
        :param links:
        :param upNodes:
        :return:
        """
        # SMF configuration
        if mcc == None: mcc = self.conf['plmn'][:3]
        if mnc == None: mnc = self.conf['plmn'][3:]
        plmnId = {"mcc": mcc, "mnc": mnc}
        if smfName == None: smfName = "SMF-{0:06X}".format(random.randrange(0x000000, 0xFFFFFF))

        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["smfName"] = smfName

        plmnList =  self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["plmnList"]
        if plmnId not in plmnList:
            plmnList.append(plmnId)

        snssaiInfos = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
            ["configurationBase"]["snssaiInfos"]
        if sliceList != None:
            for slice in sliceList:
                sNssaiFound = False
                for item in snssaiInfos:
                    if item["sNssai"] == slice:
                        sNssaiFound = True
                        if dnnList != None:
                            for dnn in dnnList:
                                dnnFound = False
                                for dnnInfo in item["dnnInfos"]:
                                    if dnn["dnn"] == dnnInfo["dnn"]:
                                        dnnFound = True
                                        break
                                if dnnFound == False:
                                    item["dnnInfos"].append({"dnn": dnn["dnn"], "dns": dnn["dns"]})
                                else:
                                    dnnFound = False
                if sNssaiFound == False:
                    dnnInfos = []
                    for dnn in dnnList:
                        dnnInfos.append({"dnn": dnn["dnn"], "dns": dnn["dns"]})
                    snssaiInfos.append({"dnnInfos": dnnInfos, "sNssai": slice})
                else:
                    sNssaiFound = False

        userplaneInformationLinks = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
            ["configurationBase"]["userplane_information"]["links"]
        userplaneInformationUpNodes = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
            ["configurationBase"]["userplane_information"]["up_nodes"]

        if links != None:
            for link in links:
                if link not in userplaneInformationLinks:
                    userplaneInformationLinks.append(link)

        if upNodes != None:
            for key, value in upNodes.items():
                if key in userplaneInformationUpNodes:
                    if value["type"] == "AN":
                        userplaneInformationUpNodes[key] = value
                    if value["type"] == "UPF":
                        userplaneInformationUpNodes[key]["interfaces"] = value["interfaces"]
                        userplaneInformationUpNodes[key]["node_id"] = value["node_id"]
                        userplaneInformationUpNodes[key]["type"] = value["type"]
                        for newitem in value["sNssaiUpfInfos"]:
                            snssaiFound = False
                            for olditem in userplaneInformationUpNodes[key]["sNssaiUpfInfos"]:
                                if newitem["sNssai"] == olditem["sNssai"]:
                                    olditem["dnnUpfInfoList"] = newitem["dnnUpfInfoList"]
                                    snssaiFound = True
                                    break
                            if snssaiFound == False:
                                userplaneInformationUpNodes[key]["sNssaiUpfInfos"].append(newitem)
                else:
                    userplaneInformationUpNodes[key] = copy.deepcopy(value)

        smfConfigurationBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configuration"] = \
            yaml.dump(smfConfigurationBase, explicit_start=False, default_flow_style=False)
        smfUeRoutingInfoBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfoBase"]
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfo"] = \
            yaml.dump(smfUeRoutingInfoBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

        return smfName

    def smf_unset_configuration(self, dnnList: list = None, sliceList: list = None) -> None:
        if sliceList != None:
            snssaiInfos = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
                ["configurationBase"]["snssaiInfos"]
            for snssiInfosIndex, snssiInfosItem in enumerate(snssaiInfos):
                if "sNssai" in snssiInfosItem:
                    if snssiInfosItem["sNssai"] in sliceList:
                       snssaiInfos.pop(snssiInfosIndex)
                       continue

                if dnnList != None:
                    if "dnnInfos" in snssiInfosItem:
                        for dnnInfosIndex, dnnInfosItem in enumerate(snssiInfosItem["dnnInfos"]):
                            if "dnn" in dnnInfosItem:
                                for dnnItem in dnnList:
                                    if dnnInfosItem["dnn"] == dnnItem["dnn"]:
                                        snssiInfosItem["dnnInfos"].pop(dnnInfosIndex)

            userplaneInformationUpNodes = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
                ["configurationBase"]["userplane_information"]["up_nodes"]
            for nodeKey, nodeValue in userplaneInformationUpNodes.items():
                if "sNssaiUpfInfos" in nodeValue:
                    for sNssaiUpfInfosIndex, sNssaiUpfInfosItem in enumerate(nodeValue["sNssaiUpfInfos"]):
                        if "sNssai" in sNssaiUpfInfosItem:
                            if sNssaiUpfInfosItem["sNssai"] in sliceList:
                                nodeValue["sNssaiUpfInfos"].pop(sNssaiUpfInfosIndex)
                                continue
                        if dnnList != None:
                            if "dnnUpfInfoList" in sNssaiUpfInfosItem:
                                for dnnUpfInfoIndex, dnnUpfInfoItem in enumerate(sNssaiUpfInfosItem["dnnUpfInfoList"]):
                                    for dnnItem in dnnList:
                                        if dnnUpfInfoItem["dnn"] == dnnItem["dnn"]:
                                            sNssaiUpfInfosItem["dnnUpfInfoList"].pop(dnnUpfInfoIndex)

    def udm_reset_configuration(self) -> None:
        # UDM configuration
        udmConfigurationBase = self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configuration"] = \
            yaml.dump(udmConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def udm_set_configuration(self) -> None:
        # UDM configuration
        udmConfigurationBase = self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configuration"] = \
            yaml.dump(udmConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def udr_reset_configuration(self) -> None:
        # UDR configuration
        udrConfigurationBase = self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configuration"] = \
            yaml.dump(udrConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def udr_set_configuration(self) -> None:
        # UDR configuration
        udrConfigurationBase = self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configuration"] = \
            yaml.dump(udrConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def set_core_networking_parameters(self, subnetIP: str, gatewayIP: str, interfaceName: str = "ens3") -> None:
        self.running_free5gc_conf["global"]["n2network"]["masterIf"] = interfaceName
        self.running_free5gc_conf["global"]["n3network"]["masterIf"] = interfaceName
        self.running_free5gc_conf["global"]["n4network"]["masterIf"] = interfaceName
        self.running_free5gc_conf["global"]["n6network"]["masterIf"] = interfaceName
        self.running_free5gc_conf["global"]["n6network"]["subnetIP"] = subnetIP
        self.running_free5gc_conf["global"]["n6network"]["gatewayIP"] = gatewayIP
        # self.running_free5gc_conf["global"]["n6network"]["excludeIP"] = "192.168.0.254"
        self.running_free5gc_conf["global"]["n9network"]["masterIf"] = interfaceName
        # self.running_free5gc_conf["upf"]["n6if"]["ipAddress"] = "192.168.0.58"
        # "POD_IP" is a value changed in runtime inside the container in k8s
        self.running_free5gc_conf["global"]["smf"]["n4if"]["interfaceIpAddress"] = "POD_IP"
        self.running_free5gc_conf["global"]["amf"]["n2if"]["interfaceIpAddress"] = "0.0.0.0"

    def add_ue_to_db(self, plmn: str, imsi: str, key: str, ocv: str, defaultUplink: str = "1 Gbps",
                     defaultDownlink: str = "2 Gbps", gpsis: str = "msisdn-0900000000",
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        response = db.policyData.ues.amData.update(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId(),
                        "ueId": "imsi-{}".format(imsi),
                        "subscCats": ["free5gc"]
                }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response))

        response = db.policyData.ues.smData.update(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                    "_id": ObjectId(),
                    "ueId": "imsi-{}".format(imsi)
                }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.authenticationData.authenticationSubscription.update(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId()
                },
                "$set": {
                        "ueId": "imsi-{}".format(imsi),
                        "authenticationMethod":"5G_AKA",
                        "permanentKey": {
                            "permanentKeyValue": format(key),
                            "encryptionKey": 0,
                            "encryptionAlgorithm":0
                        },
                        "sequenceNumber": "16f3b3f70fc2",
                        "authenticationManagementField": "8000",
                        "milenage": {
                            "op": {
                                "opValue": "",
                                "encryptionKey": 0,
                                "encryptionAlgorithm": 0
                            }
                        },
                        "opc": {
                            "opcValue": format(ocv),
                            "encryptionKey": 0,
                            "encryptionAlgorithm": 0
                        }
                    }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response))

        db.subscriptionData.provisionedData.amData.update(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId()
                },
                "$set": {
                        "ueId": "imsi-{}".format(imsi),
                        "gpsis": [
                            format(gpsis)
                        ],
                        "subscribedUeAmbr": {
                            "uplink": format(defaultUplink),
                            "downlink": format(defaultDownlink)
                        },
                        "nssai": {
                            "defaultSingleNssais": []
                        },
                        "servingPlmnId": format(plmn)
                    }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.provisionedData.smfSelectionSubscriptionData.update(
            {
                "ueId" : "imsi-{}".format(imsi)
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId()
                },
                "$set": {
                        "ueId": "imsi-{}".format(imsi),
                        "servingPlmnId": format(plmn)
                    }
            },
            upsert = True
        )
        logger.info("db response: {}".format(response))

    def add_snssai_to_db(self, plmn: str, imsi: str, sst: str, sd: str, default: bool = True,
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        nssaiType = "singleNssais"
        if default:
            nssaiType = "defaultSingleNssais"

        response = db.policyData.ues.smData.update(
            {
                "ueId": "imsi-{}".format(imsi)
            },
            {
                "$set": {
                    "smPolicySnssaiData.{:02x}{}".format(sst, sd):
                        {
                            "snssai": {
                                "sst": int(sst), "sd": format(sd)
                                }
                        }
                }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.provisionedData.amData.update(
            {
                "ueId": "imsi-{}".format(imsi)
            },
            {
                "$push": {
                    "nssai.{}".format(nssaiType):
                        {
                            "sst": int(sst), "sd": format(sd)
                        }
                }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.provisionedData.smData.update(
            {
                "ueId": "imsi-{}".format(imsi),
                "singleNssai": {
                    "sst": format(sst),"sd": format(sd)
                }
            },
            {
                "$setOnInsert": {
                        "_id": ObjectId()
                },
                "$set": {
                        "singleNssai": {"sst": int(sst),"sd": format(sd)},
                        "ueId":"imsi-{}".format(imsi),
                        "servingPlmnId": format(plmn)
                    }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

    def add_dnn_to_db(self, imsi: str, sst: str, sd: str, dnn: str, d5qi: int, upambr: str, downambr: str,
                     mongodbServiceHost: str = "mongodb://mongodb:27017/") -> None:
        client = MongoClient(mongodbServiceHost)
        db = client["free5gc"]

        response = db.policyData.ues.smData.update(
            {
                "ueId": "imsi-{}".format(imsi)
            },
            {
                "$set": {
                    "smPolicySnssaiData.{:02x}{}.smPolicyDnnData.{}".format(sst, sd, dnn): {"dnn": format(dnn)}
                }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.provisionedData.smData.update(
            {
                "ueId": "imsi-{}".format(imsi),
                "singleNssai": {
                    "sst": int(sst),"sd": format(sd)
                }
            },
            {
                "$set": {
                        "dnnConfigurations": {
                            format(dnn): {
                                "sscModes": {
                                    "defaultSscMode": "SSC_MODE_1",
                                    "allowedSscModes": ["SSC_MODE_2","SSC_MODE_3"]
                                },
                                "5gQosProfile": {
                                    "5qi": d5qi,
                                    "arp": {
                                        "priorityLevel": 8,
                                        "preemptCap": "",
                                        "preemptVuln": ""
                                    },
                                    "priorityLevel": 8
                                 },
                                 "sessionAmbr": {
                                        "downlink": format(downambr),
                                        "uplink": format(upambr)
                                 },
                                 "pduSessionTypes": {
                                        "defaultSessionType":"IPV4",
                                        "allowedSessionTypes":["IPV4"]
                                 }
                            }
                        }
                    }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

        response = db.subscriptionData.provisionedData.smfSelectionSubscriptionData.update(
            {
                "ueId": "imsi-{}".format(imsi)
            },
            {
                "$push": {
                        "subscribedSnssaiInfos.{:02x}{}.dnnInfos".format(sst, sd): {"dnn": format(dnn)}
                    }
            },
            upsert=True
        )
        logger.info("db response: {}".format(response))

    def add_ues_from_configfile(self) -> None:
        # Add UEs subscribers
        if 'config' in self.conf and 'subscribers' in self.conf['config'] and "plmn" in self.conf:
            if 'subscribers' not in self.running_free5gc_conf:
                self.running_free5gc_conf['subscribers'] = []
            for s in self.conf['config']['subscribers']:
                if s not in self.running_free5gc_conf['subscribers']:
                    self.running_free5gc_conf['subscribers'].append(s)

    def core_nsd(self) -> str:
        logger.info("Creating Core NSD(s)")
        core_v = next((item for item in self.conf['vims'] if item['core']), None)
        if core_v == None:
            raise ValueError("Core VIM in msg doesn't exist")
        vim_net_mapping = [
            {'vld': 'data', 'vim_net': core_v['wan']['id'], 'name': 'ens4', "mgt": True, 'k8s-cluster-net': 'data_net'}
        ]
        nsd_names = []

        self.setVnfd('core', vls=vim_net_mapping)

        # set networking parameters for 5GC core running configuration files
        self.set_core_networking_parameters( interfaceName = "ens3", subnetIP = "192.168.0.0",
                                             gatewayIP = "192.168.0.254" )

        # reset configuration
        self.amf_reset_configuration()
        self.ausf_reset_configuration()
        self.n3iwf_reset_configuration()
        self.nrf_reset_configuration()
        self.nssf_reset_configuration()
        self.pcf_reset_configuration()
        self.smf_reset_configuration()
        self.udm_reset_configuration()
        self.udr_reset_configuration()

        # set configuration
        tacList = []
        sliceList = []
        dnnList = []

        smfName = "SMF-{0:06X}".format(random.randrange(0x000000, 0xFFFFFF))
        n3iwfId = random.randint(1, 9999)
        nssfName = "{0:06x}".format(random.randrange(0x000000, 0xFFFFFF))


        # add tac, slice and dnn ids to all tacs of all vims
        if "vims" in self.conf:
            for vim in self.conf["vims"]:
                if "tacs" in vim:
                    # add tac id to tacList
                    for tac in vim["tacs"]:
                        tacList.append(tac["id"])
                        if len(self.defaultSliceList) != 0:
                            for s in self.defaultSliceList:
                                self.smf_set_configuration(smfName=smfName, dnnList=self.defaultDnnList,
                                                       sliceList=[s])
                            self.n3iwf_set_configuration(n3iwfId=n3iwfId, tac=tac["id"],
                                                         sliceSupportList=self.defaultSliceList)
                            self.nssf_set_configuration(nssfName=nssfName, sliceList=self.defaultSliceList,
                                                        tac=tac["id"])

                        if "slices" in tac:
                            # add slice to sliceList
                            tacSliceList = []
                            for slice in tac["slices"]:
                                s = {"sd": slice["sd"], "sst": slice["sst"]}
                                if s not in tacSliceList:
                                    tacSliceList.append(s)
                                if s not in sliceList:
                                    sliceList.append(s)
                                if "dnnList" in slice:
                                    # add dnn to dnnList
                                    dnnSliceList = []
                                    for dnn in slice["dnnList"]:
                                        if dnn not in dnnSliceList:
                                            dnnSliceList.append(dnn)
                                        if dnn not in dnnList:
                                            dnnList.append(dnn)

                                    self.smf_set_configuration(smfName=smfName, dnnList=dnnSliceList, sliceList=[s])

                            self.n3iwf_set_configuration(n3iwfId=n3iwfId, tac=tac["id"], sliceSupportList=tacSliceList)
                            self.nssf_set_configuration(nssfName=nssfName, sliceList=tacSliceList, tac=tac["id"])

                    # if there are not "tac" or "slices" associated with tac (excluding default values),
                    # it executes a default configuration
                    if len(tacList) == 0 or len(sliceList) == 0:
                        self.smf_set_configuration(smfName=smfName, dnnList=dnnList, sliceList=sliceList)
                        self.n3iwf_set_configuration(n3iwfId=n3iwfId)
                        self.nssf_set_configuration(nssfName=nssfName)

        if len(self.defaultSliceList) != 0:
            sliceList.extend(self.defaultSliceList)
            dnnList.extend(self.defaultDnnList)
        self.amf_set_configuration(supportedTacList = tacList, snssaiList = sliceList, dnnList = dnnList)

        self.ausf_set_configuration()
        self.nrf_set_configuration()
        self.pcf_set_configuration()
        # SMF: "nodes" and "links" will be configured during "day2", because ip addresses are not known in this phase
        #self.smf_set_configuration(dnnList = dnnList, sliceList = sliceList)
        self.udm_set_configuration()
        self.udr_set_configuration()
        # for tac in tacList:
        #     self.n3iwf_set_configuration(tac = tac, sliceSupportList = sliceList)
        #     self.nssf_set_configuration(sliceList=sliceList, tac=tac)

        # activation of 5G core modules
        self.running_free5gc_conf["deployAMF"] = True
        self.running_free5gc_conf["deployAUSF"] = True
        self.running_free5gc_conf["deployN3IWF"] = True
        self.running_free5gc_conf["deployNRF"] = True
        self.running_free5gc_conf["deployNSSF"] = True
        self.running_free5gc_conf["deployPCF"] = True
        self.running_free5gc_conf["deploySMF"] = True
        self.running_free5gc_conf["deployUDM"] = True
        self.running_free5gc_conf["deployUDR"] = True
        self.running_free5gc_conf["deployWEBUI"] = True

        #self.add_ues_from_configfile()

        self.save_conf()

        vnfd_ = self.getVnfd('core')
        # Kubernetes
        vnfd_k8s = []
        # OpenStack
        vnfd_os = []
        for item in vnfd_ :
            if "type" in item and item["type"] in self.edge_vnfd_type:
                vnfd_os.append(item)
            else:
                vnfd_k8s.append(item)

        if vnfd_k8s:
            kdu_configs = [{
                'vnf_id': '{}_5gc'.format(self.get_id()),
                'kdu_confs': [{'kdu_name': '5gc',
                               "k8s-namespace": str(self.get_id()).lower(),
                               "additionalParams": self.running_free5gc_conf}]
            }]
            param = {
                'name': '5GC_' + str(self.conf['plmn']) + "_" + str(self.get_id()),
                'id': '5GC_' + str(self.conf['plmn']) + "_" + str(self.get_id()),
                'type': 'core'
            }
            n_obj = sol006_NSD_builder(
                vnfd_k8s, core_v, param, vim_net_mapping, knf_configs=kdu_configs
            )
            nsd_item = n_obj.get_nsd()
            nsd_item['vld'] = vim_net_mapping
            self.nsd_.append(nsd_item)
            nsd_names.append(param["name"])

        if vnfd_os:
            for item in vnfd_os:
                param = {
                    'name': str(item["id"]) + '_' + str(self.conf['plmn']) + "_" + str(self.get_id()),
                    'id': str(item["id"]) + '_' + str(self.conf['plmn']) + "_" + str(self.get_id()),
                    'type': 'core'
                }
                n_obj = sol006_NSD_builder([item], core_v, param, vim_net_mapping)
                nsd_item = n_obj.get_nsd()
                nsd_item['vld'] = vim_net_mapping
                self.nsd_.append(nsd_item)
                nsd_names.append(param["name"])

        return nsd_names

    def edge_nsd(self, tac: dict, vim: dict) -> str:
        # NOTE: no bypass here!
        logger.info("Creating EDGE NSD(s) for tac {} on vim {}".format(tac['id'], vim['name']))
        param_name_list = []

        self.set_edgeVnfd('tac', tac['id'], vim)

        if vim['mgt'] != vim['wan']['id']:
            vim_net_mapping = [
                {'vld': 'mgt', 'vim_net': vim['mgt'], 'name': 'ens3', 'mgt': True},
                {'vld': 'datanet', 'vim_net': vim['wan']['id'], 'name': 'ens4', 'mgt': False}
            ]
        else:
            vim_net_mapping = [
                {'vld': 'mgt', 'vim_net': vim['wan']['id'], 'name': 'ens3', 'mgt': True}
            ]

        for type in self.edge_vnfd_type :
            param = {
                'name': '{}_{}_{}_{}'.format(type.upper(), str(tac['id']), str(self.conf['plmn']), str(self.get_id())),
                'id': '{}_{}_{}_{}'.format(type.upper(), str(tac['id']), str(self.conf['plmn']), str(self.get_id())),
                'type': '{}'.format(type)
            }
            edge_vnfd = self.getVnfd('tac', tac['id'], type)
            if not edge_vnfd:
                continue
            n_obj = sol006_NSD_builder(edge_vnfd, vim, param, vim_net_mapping)
            nsd_item = n_obj.get_nsd()
            nsd_item['tac'] = tac['id']
            nsd_item['vld'] = vim_net_mapping
            self.nsd_.append(nsd_item)
            param_name_list.append(param['name'])
        return param_name_list

    def add_ext_nsd(self, msg: dict) -> list:
        """
        Add external UPF(s) (not core) to the system
        For every TAC in the configuration message (in VIMs -> tacs) add an UPF (execution of "edge_nsd" function)
        :param msg: configuration message
        :return: list of nsd to create
        """
        # update current blue config with new data. The "pending" status is reflected in self.nsd_ status
        # if self.check_tacs(msg):
        #    raise ValueError('TACs in msg already exist')
        # self.update_confvims(msg['vims'])
        nsd_names = []
        if 'vims' in msg:
            for v in msg['vims']:
                if 'tacs' in v:
                    for b in v['tacs']:
                        nsd_n = self.edge_nsd(b, v)
                        try:
                            nsd_names.extend(nsd_n)
                        except TypeError:
                            nsd_names.append(nsd_n)
        return nsd_names

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
            'plmn': str(self.conf['plmn']),
            'upf_nodes': self.conf['config']['upf_nodes']
        }

        config = Configurator_Free5GC(
            nsd_item['descr']['nsd']['nsd'][0]['id'],
            1,
            self.get_id(),
            conf_data
        )

        res += config.dump()
        logger.info("CONF_DATA: {}".format(conf_data))
        logger.info("Module configuration built for core ")

        return res

    def edge_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        logger.info("Initializing Edge Day2 configurations")
        res = []

        conf_data = {
            'plmn': str(self.conf['plmn']),
            'upf_nodes': self.conf['config']['upf_nodes'],
            'tac': nsd_item['tac'] # tac of the node
        }

        config = Configurator_Free5GC(
            nsd_item['descr']['nsd']['nsd'][0]['id'],
            1,
            self.get_id(),
            conf_data
        )

        res += config.dump()
        logger.info("Configuration built for tac " + str(nsd_item['tac']))

        return res

    def smf_add_upf(self, smfName: str, tac: int, links: list = None, slice: dict = None, dnnInfoList: list = None):
        """
        Add UPF(s) data to the configuration of SMF and restart SMF module in Free5GC deployment

        :return: day2 object to add to "res" list for execution
        """
        logger.info("upf_nodes: {}".format(self.conf["config"]["upf_nodes"]))
        upNodes = {}
        # fill "up_nodes" with UPFs
        # TODO complete with UPFs of core
        if "config" in self.conf:
            if "upf_nodes" in self.conf["config"]:
                upfList = self.conf["config"]["upf_nodes"]
                for upf in upfList:
                    if upf["tac"] == tac:
                        # links = [{"A": "UPF-24", "B": "gNB-24"}]
                        # UPF24 = {"node_id": "192.168.0.64", "type": "UPF",
                        #         "interfaces": [{"endpoints": ["192.168.0.64"], "interfaceType": "N3", "networkInstance": "internet"}],
                        #         "sNssaiUpfInfos": [{"dnnUpfInfoList": [{"dnn": "internet", "pools": [{"cidr": "60.60.1.0/24"}]}],
                        #                             "sNssai": {"sd": "000001", "sst": 1}}]}
                        # gNB24 = {"an_ip": "192.168.0.62", "type": "AN"}
                        # upNodes = {"UPF24": UPF24, "gNB-24": gNB24}

                        dnnUpfInfoList = []
                        for dnnInfo in dnnInfoList:
                            dnnUpfInfoList.append({"dnn": dnnInfo["dnn"], "pools": dnnInfo["pools"]})
                        UPF = {"node_id": upf["ip"], "type": "UPF",
                                 "interfaces": [{"endpoints": [upf["ip"]], "interfaceType": "N3",
                                                 "networkInstance": dnnInfoList[0]["dnn"]}],
                                 "sNssaiUpfInfos": [{"dnnUpfInfoList": dnnUpfInfoList, "sNssai": slice}]}
                        upNodes["UPF-{}".format(tac)] = UPF

        vim = next((item for item in self.conf['vims']), None)
        if "vims" in self.conf:
            for vim in self.conf["vims"]:
                if "tacs" in vim:
                    for tacNode in vim["tacs"]:
                        if tacNode["id"] == tac:
                            upNodes["gNB-{}".format(tac)] = {"type": "AN", "an_ip": "{}".format(tacNode["nb_wan_ip"])}
                            break

        upNodesList = list(upNodes)
        if links == None:
            if len(upNodesList) != 2:
                logger.error("len of link is {}, links = {}".format(len(upNodesList), upNodesList))
                raise ValueError("len of link is {}, links = {}".format(len(upNodesList), upNodesList))
            links = [{"A": upNodesList[0], "B": upNodesList[1]}]

        self.smf_set_configuration(smfName = smfName, links = links, upNodes = upNodes)
        self.config_5g_core_for_reboot()

        msg2up = {'config': self.running_free5gc_conf}
        return self.core_upXade(msg2up)

    def init_day2_conf(self, msg: dict) -> list:
        logger.info("Initializing Day2 configurations")
        res = []
        tail_res = []
        self.save_conf()

        smfName = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["smfName"]

        if "vims" in msg:
            for vim in msg["vims"]:
                if "tacs" in vim:
                    for tac in vim["tacs"]:
                        dnnList = []
                        if len(self.defaultSliceList) != 0:
                            for s in self.defaultSliceList:
                                tail_res += self.smf_add_upf(smfName=smfName, tac=tac["id"], slice=s,
                                                        dnnInfoList=self.defaultDnnList)
                                for dnn in self.defaultDnnList:
                                    if dnn not in dnnList:
                                        dnnList.append(dnn)
                        if "slices" in tac:
                            for slice in tac["slices"]:
                                s = {"sd": slice["sd"], "sst": slice["sst"] }
                                if "dnnList" in slice:
                                    tail_res += self.smf_add_upf(smfName=smfName, tac=tac["id"], slice=s,
                                                            dnnInfoList=slice["dnnList"])
                                    for dnn in slice["dnnList"]:
                                        if dnn not in dnnList:
                                            dnnList.append(dnn)

                        if len(dnnList) != 0:
                            #  add default and slices Dnn list to UPF conf
                            for upf in self.conf["config"]["upf_nodes"]:
                                if upf["tac"] == tac["id"]:
                                    if "dnnList" in upf:
                                        upf["dnnList"].extend(dnnList)
                                    else:
                                        upf["dnnList"] = copy.deepcopy(dnnList)
                                    break

        for n in self.nsd_:
            if n['type'] == 'core':
                # split return a list. nsd_name is something like "amf_00101_DEGFE". We need the first characters
                nsd_type = (n["descr"]["nsd"]["nsd"][0]["name"]).split("_")
                if nsd_type and nsd_type[0] in self.edge_vnfd_type:
                    res += self.core_day2_conf(msg, n)
            elif n['type'] == 'ran':
                # if self.pnf is False:
                #    raise ValueError("PNF not supported in this blueprint instance")
                tail_res += self.ran_day2_conf(msg, n)
            elif n['type'] in self.edge_vnfd_type:
                res += self.edge_day2_conf(msg, n)

        logger.info("UPDATED!!!")

        self.save_conf()
        res = res + tail_res

        self.add_ues(msg)

        return res

    def add_ext_conf(self, msg: dict) -> list:
        """
        Day-2 for added external UPF
        :param msg:
        :return:
        """
        res = []
        if 'vims' in msg:
            for msg_vim in msg['vims']:
                if 'tacs' in msg_vim:
                    for msg_tac in msg_vim['tacs']:
                        nsd_list = []
                        for nsd_item in self.nsd_:
                            if nsd_item['tac'] == msg_tac['id'] and nsd_item['type'] in self.edge_vnfd_type:
                                nsd_list.append(nsd_item)
                        if not nsd_list: # list is empty
                            raise ValueError('nsd for tac {} not found'.format(msg_tac['id']))
                        for nsd in nsd_list:
                            res += self.edge_day2_conf({'vim': msg_vim['name'], 'tac': msg_tac['id']}, nsd)
        return res

    def del_tac_nsd(self, msg: dict) -> list:
        nsi_to_delete = super().del_tac(msg)
        for v in msg['vims']:
            if 'tacs' in v:
                for b in v['tacs']:
                    for type in self.edge_vnfd_type:
                        nsd_i = next((index for index, item in enumerate(self.nsd_) if item['tac'] == b['id'] and item['type'] == type), None)
                        if nsd_i is None:
                            raise ValueError('nsd not found')
                        nsi_to_delete.append(self.nsd_[nsd_i]['nsi_id'])
                        self.nsd_.pop(nsd_i)
        return nsi_to_delete

    def add_tac_conf(self, msg: dict) -> list:
        res = []
        for msg_vim in msg['vims']:
            if 'tacs' in msg_vim:
                for msg_tac in msg_vim['tacs']:
                    for nsd_item in self.nsd_:
                        if "tac" in nsd_item and nsd_item['tac'] == msg_tac['id']:
                            if nsd_item['type'] == 'ran':
                                res += self.ran_day2_conf({'vim': msg_vim['name'], 'tac': msg_tac['id']}, nsd_item)
                                break
                            if nsd_item["type"] in self.edge_vnfd_type:
                                res += self.edge_day2_conf({'vim': msg_vim['name'], 'tac': msg_tac['id']}, nsd_item)

                    if len(self.defaultSliceList) != 0 and len(self.defaultDnnList) != 0:
                        smfName = \
                        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"][
                            "smfName"]
                        for slice in self.defaultSliceList:
                            res += self.smf_add_upf(smfName=smfName, tac=msg_tac["id"], slice=slice,
                                         dnnInfoList=self.defaultDnnList)
        return res

    def add_slice(self, msg: dict) -> list:
        res = []
        tail_res = []

        tacList = []
        sliceList = []
        dnnList = []

        # add callback IP in self.conf
        if "callback" in msg:
            self.conf["callback"] = msg["callback"]

        amfId = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"] \
            ["servedGuamiList"][0]["amfId"]
        smfName= self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["smfName"]
        n3iwfId = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configurationBase"] \
            ["N3IWFInformation"]["GlobalN3IWFID"]["N3IWFID"]
        nssfName = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["nssfName"]

        if "config" in msg:
            if "slices" in msg["config"]:
                for extSlice in msg["config"]["slices"]:
                    dnnSliceList = []
                    slice = {"sd": extSlice["sd"], "sst": extSlice["sst"]}
                    sliceList.append(slice)
                    if "dnnList" in extSlice:
                        for dnn in extSlice["dnnList"]:
                            dnnSliceList.append(dnn)
                            dnnList.append(dnn)

                    self.smf_set_configuration(smfName=smfName, dnnList=dnnSliceList, sliceList=[slice])

                    # add DNNs to upf configuration
                    if "tacList" in extSlice:
                        for tac in extSlice["tacList"]:
                            if len(dnnSliceList) != 0:
                                for upf in self.conf["config"]["upf_nodes"]:
                                    if upf["tac"] == tac["id"]:
                                        if "dnnList" in upf:
                                            upf["dnnList"].extend(dnnSliceList)
                                        else:
                                            upf["dnnList"] = copy.deepcopy(dnnSliceList)
                                        break

                            tacList.append(tac["id"])
                            self.n3iwf_set_configuration(n3iwfId=n3iwfId, tac=tac["id"], sliceSupportList=[slice])
                            self.nssf_set_configuration(nssfName=nssfName, sliceList=[slice], tac=tac["id"])
                            tail_res += self.smf_add_upf(smfName=smfName, tac=tac["id"], slice=slice, dnnInfoList=extSlice["dnnList"])
                self.amf_set_configuration(amfId=amfId, supportedTacList = tacList, snssaiList = sliceList, dnnList = dnnList)

                # Add DNN to UPF
                for tacItem in tacList:
                    for nsd_item in self.nsd_:
                        if "tac" in nsd_item and nsd_item['tac'] == tacItem:
                            if nsd_item['type'] in self.edge_vnfd_type:
                                conf_data = {
                                    'plmn': str(self.conf['plmn']),
                                    'upf_nodes': self.conf['config']['upf_nodes'],
                                    'tac': tacItem # tac of the node
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

                self.config_5g_core_for_reboot()
                msg2up = {'config': self.running_free5gc_conf}
                res += tail_res + self.core_upXade(msg2up)

        self.add_ues(msg)

        return res

    def add_ues(self, msg: dict) -> list:
        res = []

        mongoDbPath = None
        if "config" in self.conf:
            if "mongodb" in self.conf["config"]:
                mongoDbPath = "mongodb://{}:27017/".format(self.conf["config"]["mongodb"])

        if "config" in msg and "plmn" in msg:
            if "subscribers" in msg["config"]:
                for subscriber in msg["config"]["subscribers"]:
                    plmn = msg["plmn"]
                    imsi = subscriber["imsi"]
                    if "k" in subscriber and "opc" in subscriber:
                        key = subscriber["k"]
                        opc = subscriber["opc"]

                        self.add_ue_to_db(plmn=plmn, imsi=imsi, key=key, ocv=opc, mongodbServiceHost=mongoDbPath)

                    if "snssaiList" in subscriber:
                        for snssaiElem in subscriber["snssaiList"]:
                            sst = snssaiElem["sst"]
                            sd = snssaiElem["sd"]
                            default = snssaiElem["default"]

                            self.add_snssai_to_db(plmn=plmn, imsi=imsi, sst=sst, sd=sd, default=default,
                                                  mongodbServiceHost=mongoDbPath)

                            if "dnnList" in snssaiElem:
                                for dnnElem in snssaiElem["dnnList"]:
                                    dnn = dnnElem["dnn"]
                                    uplinkAmbr = dnnElem["uplinkAmbr"]
                                    downlinkAmbr = dnnElem["downlinkAmbr"]
                                    default5qi = dnnElem["default5qi"]

                                    self.add_dnn_to_db(imsi=imsi, sst=sst, sd=sd, dnn=dnn, d5qi=default5qi,
                                                       upambr=uplinkAmbr, downambr=downlinkAmbr,
                                                       mongodbServiceHost=mongoDbPath)

                                    # complete with flowRules

        return res

    def del_slice(self, msg: dict) -> list:
        res = []
        tail_res = []

        # add callback IP in self.conf
        if "callback" in msg:
            self.conf["callback"] = msg["callback"]

        if "config" in msg:
            if "slices" in msg["config"]:
                for extSlice in msg["config"]["slices"]:
                    dnnSliceList = []
                    sliceList = [{"sd": extSlice["sd"], "sst": extSlice["sst"]}]
                    if "dnnList" in extSlice:
                        for dnn in extSlice["dnnList"]:
                            dnnSliceList.append(dnn)
                    self.amf_unset_configuration(sliceList,dnnSliceList)
                    self.smf_unset_configuration(dnnSliceList, sliceList)
                    self.n3iwf_unset_configuration(sliceList)
                    self.nssf_unset_configuration(sliceList)

                    # remove DNNs to upf configuration
                    if "tacList" in extSlice:
                        for tac in extSlice["tacList"]:
                            removingDnnList = []
                            if len(dnnSliceList) != 0:
                                for upf in self.conf["config"]["upf_nodes"]:
                                    if upf["tac"] == tac["id"]:
                                        if "dnnList" in upf:
                                            for dnnIndex, dnnElem in enumerate(upf["dnnList"]):
                                                if dnnElem in dnnSliceList:
                                                    removingDnnList.append(dnnElem)
                                                    upf["dnnList"].pop(dnnIndex)

                            if len(removingDnnList) != 0:
                                for nsd_item in self.nsd_:
                                    if "tac" in nsd_item and nsd_item['tac'] == tac["id"]:
                                        if nsd_item['type'] in self.edge_vnfd_type:
                                            conf_data = {
                                                'plmn': str(self.conf['plmn']),
                                                'upf_nodes': self.conf['config']['upf_nodes'],
                                                'tac': tac["id"],  # tac of the node
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

                self.config_5g_core_for_reboot()

                msg2up = {'config': self.running_free5gc_conf}
                res += self.core_upXade(msg2up) + tail_res

        return res

    def config_5g_core_for_reboot(self) -> None:
        """
        This method modifies the running configuration of all 5G core modules.
        So k8s, after loading it, restarts each module
        :return:
        """
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]\
            ["reboot"] = random.randrange(0, 9999)
        self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"]\
            ["reboot"] = random.randrange(0, 9999)
        self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configurationBase"]\
            ["reboot"] = random.randrange(0, 9999)
        self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]\
            ["reboot"] = random.randrange(0, 9999)
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]\
            ["reboot"] = random.randrange(0, 9999)
        self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configurationBase"]\
            ["reboot"] = random.randrange(0, 9999)
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]\
            ["reboot"] = random.randrange(0, 9999)
        self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configurationBase"]\
            ["reboot"] = random.randrange(0, 9999)
        self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configurationBase"]\
            ["reboot"] = random.randrange(0, 9999)

        amfConfigurationBase = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configuration"] = \
            yaml.dump(amfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        ausfConfigurationBase = self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configuration"] = \
            yaml.dump(ausfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        n3iwfConfigurationBase = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configuration"] = \
            yaml.dump(n3iwfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        nrfConfigurationBase = self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configuration"] = \
            yaml.dump(nrfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        nssfConfigurationBase = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configuration"] = \
            yaml.dump(nssfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        pcfConfigurationBase = self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configuration"] = \
            yaml.dump(pcfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        smfConfigurationBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configuration"] = \
            yaml.dump(smfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        udmConfigurationBase = self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configuration"] = \
            yaml.dump(udmConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        udrConfigurationBase = self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configuration"] = \
            yaml.dump(udrConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)


    def core_upXade(self, msg: dict) -> list:
        ns_core = next((item for item in self.nsd_ if item['type'] == 'core'), None)
        if ns_core is None:
            raise ValueError('core NSD not found')
        return self.kdu_upgrade(ns_core['descr']['nsd']['nsd'][0]['name'], msg['config'], nsi_id=ns_core['nsi_id'])

    def kdu_upgrade(self, nsd_name: str, conf_params: dict, vnf_id="1", kdu_name="5gc", nsi_id=None):
        # if "smf" in conf_params:
        #     update_smf = False
        #     if "userplane_information" in conf_params["smf"]:
        #         if "up_nodes" in conf_params["smf"]["userplane_information"]:
        #             self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]\
        #                 ["userplane_information"]["up_nodes"].update(conf_params["smf"]["userplane_information"]["up_nodes"])
        #             update_smf = True
        #         if "links" in conf_params["smf"]["userplane_information"]:
        #             self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]\
        #                 ["userplane_information"]["links"].extend(conf_params["smf"]["userplane_information"]["links"])
        #             update_smf = True
        #
        #         if update_smf:
        #             smfConfigurationBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]
        #             self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configuration"] = \
        #                 yaml.dump(smfConfigurationBase, explicit_start=False, default_flow_style=False)

        if 'kdu_model' not in conf_params:
            conf_params['kdu_model'] = self.chart

        #self.pending_updates = conf_params
        res = [
            {
                'ns-name': nsd_name,
                'primitive_data': {
                    'member_vnf_index': vnf_id,
                    'kdu_name': kdu_name,
                    'primitive': 'upgrade',
                    'primitive_params': self.running_free5gc_conf
                }
            }
        ]
        if nsi_id is not None:
            res[0]['nsi_id'] = nsi_id
        #self.config_content = {}

        # TODO check if the the following commands are needed
        if hasattr(self, "nsi_id"):
            if self.nsi_id is not None:
                for r in res:
                    r['nsi_id'] = self.nsi_id

        return res

    # def add_ext_to_core_and_update(self, msg: dict) -> list:
    #     logger.info("Add external UPF modules addresses to Core")
    #     pfcp = []
    #     config = {}
    #     '''
    #     if 'vims' in msg:
    #         for v in msg['vims']:
    #             if 'tacs' in v:
    #                 for t in v['tacs']:
    #                     if 'upf_ip' in t:
    #                         pfcp.append({'addr': t['upf_ip'], 'dnn': 'internet'})
    #             if len(pfcp) > 0:
    #                 upf = {'pfcp': pfcp}
    #                 config['smfconfigmap'] = {'upf': upf}
    #     '''
    #     self.running_free5gc_conf.update(config)
    #     self.save_conf()
    #     logger.debug("msg['config'] : {}".format(self.running_free5gc_conf))
    #     #return self.core_upXade({'config': self.running_free5gc_conf})
    #     return []

    def get_ip(self) -> None:
        logger.info('Getting IP addresses of VNFIs (ext version)')
        for n in self.nsd_:
            if n['type'] in self.edge_vnfd_type:
                try:
                    vim = next((item for item in self.conf['vims'] if item['name'] == n['vim']), None)
                    if vim is None:
                        raise ValueError("get_ip vim is None")
                    tac = next((item for item in vim['tacs'] if item['id'] == n['tac']), None)
                    if tac is None:
                        raise ValueError("get_ip tac is None")

                    logger.info('(EXT)Setting IP addresses for {} nsi for TAC {} on VIM {}'
                                .format(n['type'].upper(), tac['id'], vim['name']))

                    # retrieving vlds from the vnf
                    vnfd = self.getVnfd('tac', tac['id'], n['type'])[0]
                    vld_names = [i['vld'] for i in vnfd['vl']]
                    vlds = get_ns_vld_ip(n['nsi_id'], vld_names)

                    if len(vld_names) == 1:
                        tac['{}_ip'.format(n['type'])] = vlds["mgt"][0]['ip']
                        logger.info('{}(1) ip: {}'.format(n['type'].upper(), tac['{}_ip'.format(n['type'])]))
                    elif 'datanet' in vld_names:
                        tac['{}_ip'.format(n['type'])] = vlds["datanet"][0]['ip']
                        logger.info('{}(2) ip: {}'.format(n['type'].upper(), tac['{}_ip'.format(n['type'])]))
                    else:
                        raise ValueError('({})mismatch in the enb interfaces'.format(n['type']))

                    if '{}_nodes'.format(n['type']) not in self.conf['config']: self.conf['config']['{}_nodes'.format(n['type'])] = []
                    self.conf['config']['{}_nodes'.format(n['type'])].append({
                        'ip': tac['{}_ip'.format(n['type'])],
                        'nsi_id': n['nsi_id'],
                        'ns_id': n['descr']['nsd']['nsd'][0]['id'],
                        'type': n['type'],
                        'tac': n['tac'] if 'tac' in n else None
                    })
                    logger.info("node ip: {}".format(tac['{}_ip'.format(n['type'])]))
                    logger.info("nodes: {}".format(self.conf['config']['{}_nodes'.format(n['type'])]))
                except Exception as e:
                    logger.error("({})Exception in getting IP addresses from EDGE nsi: {}"
                                 .format(n['type'].upper(), str(e)))
                    raise ValueError(str(e))

        # saving operation yet done in "super().get_ip()"
        # self.save_conf()

        super().get_ip()


    def get_ip_core(self, n) -> None:
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
                    'tac': n['tac'] if 'tac' in n else None
                })

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
