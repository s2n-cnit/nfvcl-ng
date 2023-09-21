import copy
from typing import Union, Dict
from pydantic import BaseModel, parse_obj_as
from main import *
from utils.log import create_logger

# create logger
logger = create_logger('Configurator_Free5GC_Core')

class NoAliasDumper(yaml.SafeDumper):
    """
    Used to remove "anchors" and "aliases" from yaml file
    """
    def ignore_aliases(self, data):
        return True


class SstConvertion():
    sstType = {"EMBB": 1, "URLLC": 2, "MMTC": 3}

    def __init__(self) -> None:
        pass

    @classmethod
    def to_string(cls, value: int = None) -> str:
        return next((k for k, v in cls.sstType.items() if v == value), None)

    @classmethod
    def to_int(cls, value: str = None) -> int:
        return next((v for k,v in cls.sstType.items() if k == value), None)


class Configurator_Free5GC_Core():
    def __init__(self, running_free5gc_conf: string = None, conf: dict = None) -> None:
        if running_free5gc_conf == None:
            raise ValueError("The Free5GC configuration file is empty")
        self.running_free5gc_conf = running_free5gc_conf
        if conf == None:
            raise ValueError("The \"conf\" configuration is empty")
        self.conf = conf
        # used for NSSF configuration
        self.nsiIdCounter = 0
        try:
            self.smfName = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]\
                ["configurationBase"]["smfName"]
        except Exception:
            self.smfName = "SMF-{0:06X}".format(random.randrange(0x000000, 0xFFFFFF))
        try:
            self.n3iwfId = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]\
                ["configurationBase"]["N3IWFInformation"]["Name"]
        except Exception:
            self.n3iwfId = random.randint(1, 9999)
        try:
            self.nssfName = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]\
                ["configurationBase"]["nssfName"]
        except Exception:
            self.nssfName = "{0:06x}".format(random.randrange(0x000000, 0xFFFFFF))

    def get_dnn_list_from_net_names(self, msg: dict = None, netNames: list = None, addPoolsData: bool = True) -> List:
        """
        It works reading the msg ("slice-intent" message) and match netNames to "data_nets" section
        ex: ["internet"] -> [
        {
          "dnn": "internet",
          "dns": "8.8.8.8",
          "pools": [{"cidr": "10.60.0.0/16"}]
        }
        ]
        """
        logger.info(" -> netNames: {} -- addPoolsData: {}".format(netNames, addPoolsData))
        if msg is None or netNames is None:
            raise ValueError("configuration or network names of datanets are not valid")
        if addPoolsData:
            dnnList = [{"dnn": i["dnn"], "dns": i["dns"], "pools": i["pools"]} for i
                       in msg["config"]["network_endpoints"]["data_nets"] if i["net_name"] in netNames]
        else:
            dnnList = [{"dnn": i["dnn"], "dns": i["dns"]} for i
                   in msg["config"]["network_endpoints"]["data_nets"] if i["net_name"] in netNames]

        logger.info(" -->> dnnList: {}".format(dnnList))
        return dnnList

    def get_dnn_names_from_slice(self, msg: dict = None, sliceType: str = None, sliceId: str = None) -> List:
        """
        """
        if msg is None or sliceType is None or sliceId is None:
            raise ValueError("configuration or slice values are not valid")
        return  next((i["dnnList"] for i in msg["config"]["sliceProfiles"] if i["sliceId"] == sliceId and
                         i["sliceType"] == sliceType ), None)


    def amf_reset_configuration(self) -> None:
        """
        AMF reset configuration
        """
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]["servedGuamiList"] = []
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]["supportTaiList"] = []
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]["plmnSupportList"] = []
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]["supportDnnList"] = []
        amfConfigurationBase = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configuration"] = \
            yaml.dump(amfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def getANewNsiId(self) -> int:
        """
        get a new value for NSI ID (used by NSSF)
        """
        self.nsiIdCounter += 1
        return self.nsiIdCounter

    def amf_set_configuration(self, mcc: str, mnc: str, supportedTacList: list = None, amfId: str = None,
                              snssaiList: list = None, dnnList: list = None) -> str:
        """
        Configure AMF configMap
        :param supportedTacList: [24]
        :param amfId: "cafe01"
        :param mcc: "001"
        :param mnc: "01"
        :param snssaiList: ex. [{"sst": 1, "sd": "000001"}]
        :param dnnList: ex. [{"dnn": "internet", "dns": { "ipv4": "8.8.8.8"}}]
        :return: amfId
        """
        if mcc == None or mnc == None:
            raise ValueError("mcc () or mnc () is None".format(mcc, mnc))
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
                        item = {"sst": snssaiItem["sst"], "sd": snssaiItem["sd"]}
                        if item not in plmnIdSupportItem["snssaiList"]:
                            plmnIdSupportItem["snssaiList"].append(item)
                break
        if plmnFound == False:
            plmnIdSupportItem = {"plmnId": plmnId, "snssaiList": []}
            if snssaiList != None:
                for snssaiItem in snssaiList:
                    item = {"sst": snssaiItem["sst"], "sd": snssaiItem["sd"]}
                    if item not in plmnIdSupportItem["snssaiList"]:
                        plmnIdSupportItem["snssaiList"].append(item)
            plmnSupportList.append(plmnIdSupportItem)

        supportDnnList = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"] \
            ["supportDnnList"]
        if dnnList != None:
            for dnnItem in dnnList:
                if dnnItem["dnn"] not in supportDnnList:
                    supportDnnList.append(dnnItem["dnn"])

        amfConfigurationBase = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configuration"] = \
            yaml.dump(amfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        return amfId

    def amf_unset_configuration(self, mcc: str, mnc :str, snssaiList: list = None, dnnList: list = None) -> None:
        """
        AMF unset configuration
        """
        if mcc == None or mnc == None:
            raise ValueError("mcc () or mnc () is None".format(mcc, mnc))
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
        """
        AUSF reset
        """
        self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"]["plmnSupportList"] = []
        ausfConfigurationBase = self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configuration"] = \
            yaml.dump(ausfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def ausf_set_configuration(self, mcc: str, mnc: str) -> None:
        """
        AUSF configuration
        """
        if mcc == None or mnc == None:
            raise ValueError("mcc () or mnc () is None".format(mcc, mnc))
        plmnSupportItem = {"mcc": mcc, "mnc": mnc}
        plmnSupportList = self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"] \
            ["plmnSupportList"]
        if plmnSupportItem not in plmnSupportList:
            plmnSupportList.append(plmnSupportItem)
        ausfConfigurationBase = self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configuration"] = \
            yaml.dump(ausfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def n3iwf_reset_configuration(self) -> None:
        """
        N3IWF configuration
        """
        self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configurationBase"]["N3IWFInformation"] = \
            {"GlobalN3IWFID": {"PLMNID": {"MCC": "", "MNC": ""}, "N3IWFID": ""}, "Name": "",
             "SupportedTAList": []}
        n3iwfConfigurationBase = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"][
            "configurationBase"]
        self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configuration"] = \
            yaml.dump(n3iwfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def n3iwf_set_configuration(self, mcc: str, mnc: str, name: str = None, tac: int = -1,
                                sliceSupportList: list = None, n3iwfId: int = -1) -> str:
        """
        N3IWF configuration
        """
        if mcc == None or mnc == None:
            raise ValueError("mcc () or mnc () is None".format(mcc, mnc))
        # if name == None: name = str(random.choice(string.ascii_lowercase) for i in range(6))
        if name == None: name = "{0:06x}".format(random.randrange(0x000000, 0xFFFFFF))
        if n3iwfId == -1: n3iwfId = random.randint(1, 9999)

        n3iwfInformation = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configurationBase"] \
            ["N3IWFInformation"]
        n3iwfInformation["GlobalN3IWFID"]["N3IWFID"] = n3iwfId
        n3iwfInformation["GlobalN3IWFID"]["PLMNID"]["MCC"] = mcc
        n3iwfInformation["GlobalN3IWFID"]["PLMNID"]["MNC"] = mnc
        n3iwfInformation["Name"] = name

        if tac != -1:
            taFound = False
            TAC = "{:06x}".format(tac)
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
                            sTAItem = [{"PLMNID": {"MCC": mcc, "MNC": mnc}, "TAC": TAC,
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
        """
        N3IWF unset configuration
        """
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
                                        slice = {"sd": taiSliceItem["SNSSAI"]["SD"],
                                                 "sst": taiSliceItem["SNSSAI"]["SST"]}
                                        if slice in sliceSupportList:
                                            broadcastItem["TAISliceSupportList"].pop(taiSliceIndex)

        n3iwfConfigurationBase = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"][
            "configurationBase"]
        self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configuration"] = \
            yaml.dump(n3iwfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def nrf_reset_configuration(self) -> None:
        """
        NRF reset configuration
        """
        self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]["DefaultPlmnId"] = {}
        nrfConfigurationBase = self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configuration"] = \
            yaml.dump(nrfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def nrf_set_configuration(self, mcc: str, mnc: str):
        """
        NRF configuration
        """
        if mcc == None or mnc == None:
            raise ValueError("mcc () or mnc () is None".format(mcc, mnc))
        self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]["DefaultPlmnId"] = \
            {"mcc": mcc, "mnc": mnc}
        nrfConfigurationBase = self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configuration"] = \
            yaml.dump(nrfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def nssf_reset_configuration(self) -> None:
        """
        NSSF configuration
        """
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"][
            "supportedPlmnList"] = []
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["nsiList"] = []
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

    def nssf_set_configuration(self, mcc: str, mnc: str, operatorName: str = "CNIT", nssfName: str = None,
                               sliceList: list = None, nfId: str = None, tac: int = -1) -> str:
        """
        NSSF configuration
        """
        if nssfName == None: nssfName = "{0:06x}".format(random.randrange(0x000000, 0xFFFFFF))
        if nfId == None: nfId = "{:035d}".format(random.randrange(0x0, 0x13426172C74D822B878FE7FFFFFFFF))
        sstSdList = []
        if sliceList != None:
            for slice in sliceList:
                sstSdList.append({"sst": slice["sst"], "sd": slice["sd"]})

        nrfUri = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["nrfUri"]

        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["nssfName"] = nssfName

        supportedPlmnList = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"] \
            ["supportedPlmnList"]
        supportedPlmnItem = {"mcc": mcc, "mnc": mnc}
        if supportedPlmnItem not in supportedPlmnList:
            supportedPlmnList.append(supportedPlmnItem)

        nsiList = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["nsiList"]
        if sliceList != None:
            for slice in sliceList:
                elem = {"snssai": {"sst": slice["sst"], "sd": slice["sd"]}, "nsiInformationList":
                    [{"nrfId": "{}/nnrf-nfm/v1/nf-instance".format(nrfUri), "nsiId": self.getANewNsiId()}]}
                nsiList.append(elem)

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
                            if {"sd": slice["sd"], "sst": slice["sst"]} not in supportedNssaiInPlmnItem[
                                "supportedSnssaiList"]:
                                supportedNssaiInPlmnItem["supportedSnssaiList"].append(
                                    {"sd": slice["sd"], "sst": slice["sst"]})
            if plmnIdFound == False:
                supportedNssaiInPlmnList.append({"plmnId": plmnId,
                                                 "supportedSnssaiList": sstSdList})

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
                                    item["supportedSnssaiList"].append({"sst": slice["sst"], "sd": slice["sd"]})
                        break
                if amfItem["nfId"] == nfId:
                    nfIdFound = True
                    if taiFound == False:
                        supportedNssaiAvailabilityData.append(
                            {"tai": "{}".format(tai), "supportedSnssaiList": sstSdList})
                        break

            if nfIdFound == False and taiFound == False:
                amfList.append({"nfId": nfId, "supportedNssaiAvailabilityData":
                    [{"tai": tai, "supportedSnssaiList": sstSdList}]})

            taiFound = False
            taList = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["taList"]
            for taItem in taList:
                if taItem["tai"] == tai:
                    taiFound = True
                    if sliceList != None:
                        for slice in sliceList:
                            if slice not in taItem["supportedSnssaiList"]:
                                taItem["supportedSnssaiList"].append({"sst": slice["sst"], "sd": slice["sd"]})
            if taiFound == False:
                taList.append(
                    {"accessType": "3GPP_ACCESS", "supportedSnssaiList": sstSdList, "tai": tai})

            mappingListFromPlmn = \
            self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"] \
                ["mappingListFromPlmn"]
            homePlmnIdFound = False
            for item in mappingListFromPlmn:
                if item["homePlmnId"] == plmnId:
                    homePlmnIdFound = True
                    if sliceList != None:
                        for slice in sliceList:
                            mappingItem = {"homeSnssai": {"sst": slice["sst"], "sd": slice["sd"]},
                                           "servingSnssai": {"sst": slice["sst"], "sd": slice["sd"]}}
                            if mappingItem not in item["mappingOfSnssai"]:
                                item["mappingOfSnssai"].append(mappingItem)
            if homePlmnIdFound == False:
                mappingOfSnssai = []
                for slice in sliceList:
                    mappingOfSnssai.append({"homeSnssai": {"sst": slice["sst"], "sd": slice["sd"]},
                                            "servingSnssai": {"sst": slice["sst"], "sd": slice["sd"]}})
                mappingListFromPlmn.append(
                    {"homePlmnId": plmnId, "mappingOfSnssai": mappingOfSnssai,
                     "operatorName": operatorName})

        nssfConfigurationBase = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configuration"] = \
            yaml.dump(nssfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

        return nfId

    def nssf_unset_configuration(self, sliceList: list = None) -> None:
        """
        NSSF unset configuration
        """
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

            mappingListFromPlmn = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"] \
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
        """
        PCF configuration
        """
        self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["pcfName"] = None
        pcfConfigurationBase = self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configuration"] = \
            yaml.dump(pcfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def pcf_set_configuration(self, pcfName: str = None) -> str:
        """
        PCF configuration
        """
        if pcfName == None: pcfName = "{:06d}".format(random.randrange(0x000000, 0xFFFFFF))
        self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["pcfName"] = pcfName
        pcfConfigurationBase = self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configuration"] = \
            yaml.dump(pcfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        return pcfName

    def smf_reset_configuration(self) -> None:
        """
        SMF configuration
        """
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["smfName"] = ""
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["snssaiInfos"] = []

        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["plmnList"] = []
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"] \
            ["userplaneInformation"] = {"upNodes": {}, "links": []}

        # The empty lists of "upNodes" and "links" makes SMF instable to start. So don't start SMF ("deploySMF"=False)
        # before have a full configuration
        self.running_free5gc_conf["deploySMF"] = False

        smfConfigurationBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configuration"] = \
            yaml.dump(smfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfoBase"] = dict()
        smfUeRoutingInfoBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfoBase"]
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfo"] = \
            yaml.dump(smfUeRoutingInfoBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def smf_routing_set_configuration(self, members: list = None, links: list = None, specificPaths: list = None,
                                      groupName: str = None):
        """
        smf routing set configuration.
        Configuration for "uerounting.yaml" in case ULCL (Uplink Classifier) is enabled
        :param members:
            list of UEs imsi. ex. ["imsi-208930000000003", "imsi-208930000000004"]
        :param links:
            list of links as set in SMF configuration. ex. [{"A": "gNB1", "B": "UPF-core"}, {"A": "UPF-core", "B": "UPF-1"}]
        :param specificPaths:
            list of specific path. ex. [{"dest": "8.8.8.8/32", "path": ["UPF-1", "UPF-2"]}]
        :param groupName:
            name (string) of the sub-configuration group. ex. "UE1"
        """
        smfUeRoutingInfoBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfoBase"]

        if groupName == None:
            logger.warn("group name is empty")
            return

        if smfUeRoutingInfoBase is None or type(smfUeRoutingInfoBase) is not dict:
            smfUeRoutingInfoBase = dict()
        if groupName not in smfUeRoutingInfoBase:
            smfUeRoutingInfoBase[groupName] = dict()
        group = smfUeRoutingInfoBase[groupName]
        if members is not None:
            if "members" not in group:
                group["members"] = []
            for elem in members:
                if "imsi-{}".format(elem) not in group["members"]:
                    group["members"].append("imsi-{}".format(elem))
        if links is not None:
            if "topology" not in group:
                group["topology"] = []
            group["topology"].extend(x for x in links if x not in group["topology"])
        if specificPaths is not None:
            if "specificPath" not in group:
                group["specificPath"] = []
            group["specificPath"].extend(x for x in specificPaths if x not in group["specificPath"])


        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfo"] = \
            yaml.dump(smfUeRoutingInfoBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def smf_routing_unset_configuration(self, members: list = None, links: list = None, specificPaths: list = None,
                                      groupName: str = "UE1", tac: int = None ):
        """
        smf routing unset configuration.
        Configuration for "uerouting.yaml" in case ULCL (Uplink Classifier) is enabled
        :param members:
            list of UEs imsi. ex. ["imsi-208930000000003", "imsi-208930000000004"]
        :param links:
            list of links as set in SMF configuration. ex. [{"A": "gNB1", "B": "UPF-core"}, {"A": "UPF-core", "B": "UPF-1"}]
        :param specificPaths:
            list of specific path. ex. [{"dest": "8.8.8.8/32", "path": ["UPF-1", "UPF-2"]}]
        :param groupName:
            name (string) of the sub-configuration group. ex. "UE1"
        : param tac :
            tac ID (area ID). If specified, it is used to remove all links referred to this tac (area)
        """
        smfUeRoutingInfoBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfoBase"]

        if isinstance(smfUeRoutingInfoBase, dict):
            smfUeRoutingInfoBase.pop(groupName, None)

            # if groupName in smfUeRoutingInfoBase:
            #     group = smfUeRoutingInfoBase[groupName]
            #     if members is not None:
            #         if "members" in group:
            #             for elem in members:
            #                 group["members"].delete("imsi-{}".format(elem))
            #         else:
            #             raise ValueError("\"members\" list is NOT in smf routing configuration")
            #     if links is not None:
            #         if "topology" in group:
            #             for elem in links:
            #                 group["topology"].delete(elem)
            #         else:
            #             raise ValueError("\"topology\" list is NOT in smf routing configuration")
            #     if specificPaths is not None:
            #         if "specificPath" in group:
            #             for elem in specificPaths:
            #                 group["specificPath"].delete(elem)
            #     if tac is not None:
            #         if "topology" in group:
            #             for elem in group["topology"]:
            #                 if "A" in group["topology"] and group["topology"]["A"] == "UPF-{}".format(tac):
            #                     group["topology"].delete(elem)
            #                     continue
            #                 if "B" in group["topology"] and group["topology"]["B"] == "UPF-{}".format(tac):
            #                     group["topology"].delete(elem)
            #                     continue

            self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["ueRoutingInfo"] = \
                yaml.dump(smfUeRoutingInfoBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def smf_set_configuration(self, mcc: str, mnc: str, smfName: str = None, dnnList: list = None,
                              sliceList: list = None, links: list = None, upNodes: dict = None) -> str:
        """
        SMF set configuration
        :param mcc:
        :param mnc:
        :param smfName:
        :param dnnList: es. [{"dnn": "internet", "dns": "8.8.8.8"}]
        :param sliceList: es. [{"sst": 1, "sd": "000001"}]
        :param links:
        :param upNodes:
        :return:
        """
        if mcc == None or mnc == None:
            raise ValueError("mcc () or mnc () is None".format(mcc, mnc))
        plmnId = {"mcc": mcc, "mnc": mnc}
        if smfName == None: smfName = "SMF-{0:06X}".format(random.randrange(0x000000, 0xFFFFFF))

        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["smfName"] = smfName

        plmnList = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["plmnList"]
        if plmnId not in plmnList:
            plmnList.append(plmnId)

        snssaiInfos = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
            ["configurationBase"]["snssaiInfos"]
        logger.info("SNSSAIINFOS 1: {}".format(snssaiInfos))
        if sliceList != None:
            for slice in sliceList:
                logger.info("SLICE TO ADD: {}".format(slice))
                sNssaiFound = False
                for item in snssaiInfos:
                    if item["sNssai"] == slice:
                        sNssaiFound = True
                        logger.info("SLICE FOUND")
                        if dnnList != None:
                            for dnn in dnnList:
                                dnnFound = False
                                for dnnInfo in item["dnnInfos"]:
                                    if dnn["dnn"] == dnnInfo["dnn"]:
                                        dnnFound = True
                                        break
                                if dnnFound == False:
                                    item["dnnInfos"].append({"dnn": dnn["dnn"], "dns": { "ipv4": dnn["dns"]}})
                                else:
                                    dnnFound = False
                if sNssaiFound == False:
                    logger.info("SLICE NOT FOUND")
                    dnnInfos = []
                    for dnn in dnnList:
                        dnnInfos.append({"dnn": dnn["dnn"], "dns": { "ipv4": dnn["dns"]}})
                    snssaiInfos.append({"dnnInfos": dnnInfos, "sNssai": slice})
                    logger.info("SNSSAINFOS 2: {}".format(snssaiInfos))
                else:
                    sNssaiFound = False

        userplaneInformationLinks = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
            ["configurationBase"]["userplaneInformation"]["links"]
        userplaneInformationUpNodes = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
            ["configurationBase"]["userplaneInformation"]["upNodes"]

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
                        userplaneInformationUpNodes[key]["nodeID"] = value["nodeID"]
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

        # check if SMF modules is started. If a valid configuration exists, it starts SMF
        if len(userplaneInformationLinks) > 0 and len(userplaneInformationUpNodes) > 0:
            self.running_free5gc_conf["deploySMF"] = True

        smfConfigurationBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configuration"] = \
            yaml.dump(smfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

        return smfName

    def smf_unset_configuration(self, dnnList: list = None, sliceList: list = None, tacList: list = None) -> None:
        """
        SMF unset configuration
        """
        snssaiInfos = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
            ["configurationBase"]["snssaiInfos"]
        try:
            userplaneInformationLinks = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
                ["configurationBase"]["userplaneInformation"]["links"]
        except Exception as e:
            userplaneInformationLinks = []
        try:
            userplaneInformationUpNodes = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"] \
                ["configurationBase"]["userplaneInformation"]["upNodes"]
        except Exception as e:
            userplaneInformationUpNodes = {}

        if sliceList != None:
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

        if tacList != None:
            removingLinkIndexes = []
            for tac in tacList:
                upfName = "UPF-{}".format(tac["id"])
                gnbName = "gNB-{}".format(tac["id"])
                for linkIndex, linkItem in enumerate(userplaneInformationLinks):
                    list1, list2 = zip(*list(linkItem.items()))
                    if upfName in list2 or gnbName in list2:
                        removingLinkIndexes.append(linkIndex)
                for item in removingLinkIndexes[::-1]:
                    userplaneInformationLinks.pop(item)
                userplaneInformationUpNodes.pop(upfName, None)
                userplaneInformationUpNodes.pop(gnbName, None)

        smfConfigurationBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configuration"] = \
            yaml.dump(smfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)


    def udm_reset_configuration(self) -> None:
        """
        UDM configuration
        """
        udmConfigurationBase = self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configuration"] = \
            yaml.dump(udmConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def udm_set_configuration(self) -> None:
        """
        UDM configuration
        """
        udmConfigurationBase = self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configuration"] = \
            yaml.dump(udmConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def udr_reset_configuration(self) -> None:
        """
        UDR configuration
        """
        udrConfigurationBase = self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configurationBase"]
        self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configuration"] = \
            yaml.dump(udrConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)

    def udr_set_configuration(self) -> None:
        """
        UDR configuration
        """
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
        self.running_free5gc_conf["global"]["n9network"]["masterIf"] = interfaceName
        # "POD_IP" is a value changed in runtime inside the container in k8s
        self.running_free5gc_conf["global"]["smf"]["n4if"]["interfaceIpAddress"] = "POD_IP"
        self.running_free5gc_conf["global"]["amf"]["n2if"]["interfaceIpAddress"] = "0.0.0.0"

    def reset_core_configuration(self) -> None:
        self.amf_reset_configuration()
        self.ausf_reset_configuration()
        self.n3iwf_reset_configuration()
        self.nrf_reset_configuration()
        self.nssf_reset_configuration()
        self.pcf_reset_configuration()
        self.smf_reset_configuration()
        self.udm_reset_configuration()
        self.udr_reset_configuration()

    def config_5g_core_for_reboot(self, moduleNameToReboot: str = None) -> None:
        """
        This method modifies the running configuration of all 5G core modules.
        So k8s, after loading it, restarts each module

        moduleNameToReboot: module name to be rebooted, ex: "amf", "smf"...
        if None, it reboots all modules

        :return:
        """

        if moduleNameToReboot is None or moduleNameToReboot == "amf":
            self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]\
                ["reboot"] = random.randrange(0, 9999)
            amfConfigurationBase = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"]
            self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configuration"] = \
                yaml.dump(amfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        elif moduleNameToReboot is None or moduleNameToReboot == "ausf":
            self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configurationBase"]\
                ["reboot"] = random.randrange(0, 9999)
            ausfConfigurationBase = self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"][
                "configurationBase"]
            self.running_free5gc_conf["free5gc-ausf"]["ausf"]["configuration"]["configuration"] = \
                yaml.dump(ausfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        elif moduleNameToReboot is None or moduleNameToReboot == "n3iwf":
            self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configurationBase"]\
                ["reboot"] = random.randrange(0, 9999)
            n3iwfConfigurationBase = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"][
                "configurationBase"]
            self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configuration"] = \
                yaml.dump(n3iwfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        ### Don't reboot NRF
        #elif moduleNameToReboot is None or moduleNameToReboot == "nrf":
        #   self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]\
        #       ["reboot"] = random.randrange(0, 9999)
        #   nrfConfigurationBase = self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configurationBase"]
        #   self.running_free5gc_conf["free5gc-nrf"]["nrf"]["configuration"]["configuration"] = \
        #       yaml.dump(nrfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        elif moduleNameToReboot is None or moduleNameToReboot == "nssf":
            self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]\
                ["reboot"] = random.randrange(0, 9999)
            nssfConfigurationBase = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"][
                "configurationBase"]
            self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configuration"] = \
                yaml.dump(nssfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        elif moduleNameToReboot is None or moduleNameToReboot == "pcf":
            self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configurationBase"]\
                ["reboot"] = random.randrange(0, 9999)
            pcfConfigurationBase = self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configurationBase"]
            self.running_free5gc_conf["free5gc-pcf"]["pcf"]["configuration"]["configuration"] = \
                yaml.dump(pcfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        elif moduleNameToReboot is None or moduleNameToReboot == "smf":
            self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]\
                ["reboot"] = random.randrange(0, 9999)
            smfConfigurationBase = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]
            self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configuration"] = \
                yaml.dump(smfConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        elif moduleNameToReboot is None or moduleNameToReboot == "udm":
            self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configurationBase"]\
                ["reboot"] = random.randrange(0, 9999)
            udmConfigurationBase = self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configurationBase"]
            self.running_free5gc_conf["free5gc-udm"]["udm"]["configuration"]["configuration"] = \
                yaml.dump(udmConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        elif moduleNameToReboot is None or moduleNameToReboot == "udr":
            self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configurationBase"]\
                ["reboot"] = random.randrange(0, 9999)
            udrConfigurationBase = self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configurationBase"]
            self.running_free5gc_conf["free5gc-udr"]["udr"]["configuration"]["configuration"] = \
                yaml.dump(udrConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        elif moduleNameToReboot is None or moduleNameToReboot == "webui":
            self.running_free5gc_conf["free5gc-webui"]["webui"]["configuration"]\
                ["reboot"] = random.randrange(0, 9999)
            # webuiConfigurationBase = self.running_free5gc_conf["free5gc-webui"]["webui"]["configuration"][
            #     "configurationBase"]
            # self.running_free5gc_conf["free5gc-webui"]["webui"]["configuration"]["configuration"] = \
            #     yaml.dump(webuiConfigurationBase, explicit_start=False, default_flow_style=False, Dumper=NoAliasDumper)
        else:
            raise ValueError("{} is not a module of deployed Free5GC".format(moduleNameToReboot))

    def add_tacs_and_slices(self, conf: dict, smfName: string = None, n3iwfId: int = None,
            nssfName: string = None) -> None:
        """
        add_slice
        conf : it is the json message (dict) sent to Free5GC
        """
        if conf is None:
            logger.warn("Conf is None")
            return

        if "config" in conf and "plmn" in conf['config']:
            mcc = conf['config']['plmn'][:3]
            mnc = conf['config']['plmn'][3:]
        else:
            raise ValueError("config section is not in conf or plmn not specified in config section")

        # set configuration
        tacList = []
        sliceList = []
        dnnList = []

        if smfName is not None:
            self.smfName = smfName
        if n3iwfId is not None:
            self.n3iwfId = n3iwfId
        if nssfName is not None:
            self.nssfName = nssfName

        # add tac, slice and dnn ids to all tacs of all vims
        if "areas" in conf:
            # add tac id to tacList (area_id = tac)
            for area in conf["areas"]:
                tacList.append(area["id"])
                if "slices" in area:
                    # add slice to sliceList
                    tacSliceList = []
                    
                    for slice in area["slices"]:
                        s = {"sd": slice["sliceId"], "sst": SstConvertion.to_int(slice["sliceType"])}
                        if s not in tacSliceList:
                            tacSliceList.append(s)
                        if s not in sliceList:
                            sliceList.append(s)

                        # add dnn to dnnList
                        dnnSliceList = []
                        for dnn in self.get_dnn_list_from_net_names(self.conf, self.get_dnn_names_from_slice(self.conf, slice[
                                "sliceType"], slice["sliceId"])):
                            dnnSliceList.append(dnn)
                            if dnn not in dnnList:
                                dnnList.append(dnn)

                        self.smf_set_configuration(mcc=mcc, mnc=mnc, smfName=self.smfName, dnnList=dnnSliceList,
                                                   sliceList=[s])

                    self.n3iwf_set_configuration(mcc=mcc, mnc=mnc, n3iwfId=self.n3iwfId, tac=area["id"],
                            sliceSupportList=tacSliceList)
                    self.nssf_set_configuration(mcc=mcc, mnc=mnc, nssfName=self.nssfName, sliceList=tacSliceList,
                            tac=area["id"])

            # if there are not "tac" or "slices" associated with tac (excluding default values),
            # it executes a default configuration
            if len(tacList) == 0 or len(sliceList) == 0:
                self.smf_set_configuration(mcc=mcc, mnc=mnc, smfName=self.smfName, dnnList=dnnList, sliceList=sliceList)
                self.n3iwf_set_configuration(mcc=mcc, mnc=mnc, n3iwfId=self.n3iwfId)
                self.nssf_set_configuration(mcc=mcc, mnc=mnc, nssfName=self.nssfName)

        self.amf_set_configuration(mcc=mcc, mnc=mnc, supportedTacList=tacList, snssaiList=sliceList, dnnList=dnnList)

        self.ausf_set_configuration(mcc=mcc, mnc=mnc)
        self.nrf_set_configuration(mcc=mcc, mnc=mnc)
        self.pcf_set_configuration()
        # SMF: "nodes" and "links" will be configured during "day2", because ip addresses are not known in this phase
        self.udm_set_configuration()
        self.udr_set_configuration()

    def smf_del_upf(self, conf: dict, tac: int, slice: dict = None, dnnInfoList: list = None):
        """
        Del UPF(s) data to the configuration of SMF and restart SMF module in Free5GC deployment

        :return: day2 object to add to "res" list for execution
        """
        if conf is None:
            logger.warn("Conf is None")
            return

        #logger.info("upf_nodes: {}".format(conf["config"]["upf_nodes"]))

        self.smf_unset_configuration(dnnList=dnnInfoList, sliceList=[slice], tacList=[{"id": tac}])
        members = None
        # if "config" in conf and "subscribers" in conf["config"]:
        #     subscribers = conf["config"]["subscribers"]
        #     members = [elem["imsi"] for elem in subscribers if "imsi" in elem]
        self.smf_routing_unset_configuration(members=members,tac=tac, groupName="UE-gNB-{0}-UPF-{0}".format(tac))
        self.config_5g_core_for_reboot()
        #
        # msg2up = {'config': self.running_free5gc_conf}
        # return self.core_upXade(msg2up)
        return []

    def smf_add_upf(self, conf: dict, smfName: str, tac: int, links: list = None, slice: dict = None,
                    dnnInfoList: list = None):
        """
        Add UPF(s) data to the configuration of SMF and restart SMF module in Free5GC deployment
        """
        if conf is None:
            logger.warn("Conf is None")
            return

        if "config" in conf and "plmn" in conf['config']:
            mcc = conf['config']['plmn'][:3]
            mnc = conf['config']['plmn'][3:]
        else:
            raise ValueError("config section is not in conf or plmn not specified in config section")

        upNodes = {}
        coreUpfName = None
        coreSlices = []

        if "areas" in conf:
             # convert: sliceId -> sd , sliceType -> sst
            coreSlicesTmp = next((item["slices"] for item in conf["areas"] if "core" in item and item["core"]), [])
            coreSlices = list({"sd": slice["sliceId"], "sst": SstConvertion.to_int(slice["sliceType"])}
                               for slice in coreSlicesTmp)
            for area in conf["areas"]:
                if area["id"] == tac and "nb_wan_ip" in area:
                    upNodes["gNB-{}".format(tac)] = {"type": "AN", "an_ip": "{}".format(area["nb_wan_ip"])}
                    break

        # fill "upNodes" with UPFs
        if "config" in conf:
            if "upf_nodes" in conf["config"]:
                logger.info("upf_nodes: {}".format(conf["config"]["upf_nodes"]))
                upfList = conf["config"]["upf_nodes"]
                coreUpf = next((item for item in upfList if item["type"] == "core"), None)
                if coreUpf is None:
                    raise ValueError("upf of type core not exist")
                coreUpfName = "UPF-{}".format(coreUpf["area"])
                for upf in upfList:
                    logger.info(" * upf[\"area\"] = {} , tac = {}".format(upf["area"], tac))
                    if upf["area"] == tac:
                        dnnUpfInfoList = []
                        for dnnInfo in dnnInfoList:
                            logger.info("dnnInfo: {}".format(dnnInfo))
                            if slice in coreSlices and upf["type"] != "core" or "pools" not in dnnInfo:
                                logger.info("NO POOLS")
                                dnnUpfInfoList.append({"dnn": dnnInfo["dnn"]})
                            else:
                                logger.info("POOLS")
                                dnnUpfInfoList.append({"dnn": dnnInfo["dnn"], "pools": dnnInfo["pools"]})
                        interfaces = []
                        if upf["type"] == "core":
                            if "dnnList" in upf:
                                # in the case of this function is called by "add_tac"
                                for dnnElem in upf["dnnList"]:
                                    interfaces.append({"endpoints": [upf["ip"]], "interfaceType": "N9",
                                                   "networkInstance": dnnElem["dnn"]})
                            else:
                                # in the case of this function is called by "init"
                                interfaces = [{"endpoints": [upf["ip"]], "interfaceType": "N9",
                                  "networkInstance": dnnInfoList[0]["dnn"]}]
                        else:
                            if "dnnList" in upf:
                                # in the case of this function is called by "add_tac"
                                for dnnElem in upf["dnnList"]:
                                    interfaces.extend([{"endpoints": [upf["ip"]], "interfaceType": "N3",
                                    "networkInstance": dnnElem["dnn"]},
                                    {"endpoints": [upf["ip"]], "interfaceType": "N9",
                                    "networkInstance": dnnElem["dnn"]}])
                            else:
                                # in the case of this function is called by "init"
                                interfaces = [{"endpoints": [upf["ip"]], "interfaceType": "N3",
                                    "networkInstance": dnnInfoList[0]["dnn"]},
                                    {"endpoints": [upf["ip"]], "interfaceType": "N9",
                                    "networkInstance": dnnInfoList[0]["dnn"]}]
                        UPF = {"nodeID": upf["ip"], "type": "UPF", "interfaces": interfaces,
                               "sNssaiUpfInfos": [{"dnnUpfInfoList": dnnUpfInfoList, "sNssai": slice}]}
                        upNodes["UPF-{}".format(tac)] = UPF

        upNodesList = list(upNodes)
        groupName = None
        if links == None:
            if len(upNodesList) == 1:
                # UPF of the core
                logger.info("Only the core UPF, no gNB")
                groupName = None
            #if len(upNodesList) != 2:
            #    raise ValueError("len of link is {}, links = {}".format(len(upNodesList), upNodesList))
            else:
                links = [{"A": upNodesList[0], "B": upNodesList[1]}]
                links.append({"A": upNodesList[1], "B": coreUpfName})
                groupName = "UE-{}-{}".format(upNodesList[0], upNodesList[1])

        self.smf_set_configuration(mcc=mcc, mnc=mnc, smfName=smfName, links=links, upNodes=upNodes)
        members = None
        if "config" in conf and "subscribers" in conf["config"]:
            subscribers = conf["config"]["subscribers"]
            members = [elem["imsi"] for elem in subscribers if "imsi" in elem]
        self.smf_routing_set_configuration(members=members, links=links, groupName=groupName)
        self.config_5g_core_for_reboot()

        return []

    def day2_conf(self, msg: dict):
        smfName = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["smfName"]

        if "areas" in msg:
            for area in msg["areas"]:
                dnnList = []
                if "slices" in area:
                    for slice in area["slices"]:
                        s = {"sd": slice["sliceId"], "sst": SstConvertion.to_int(slice["sliceType"]) }
                        message_dnnList = self.get_dnn_list_from_net_names(self.conf,
                                self.get_dnn_names_from_slice(self.conf, slice["sliceType"], slice["sliceId"]))
                        self.smf_add_upf(conf=self.conf, smfName=smfName, tac=area["id"], slice=s,
                                                dnnInfoList=message_dnnList)
                        for dnn in message_dnnList:
                            if dnn not in dnnList:
                                dnnList.append(dnn)

                if len(dnnList) != 0:
                    #  add default and slices Dnn list to UPF conf
                    for upf in self.conf["config"]["upf_nodes"]:
                        if upf["area"] == area["id"]:
                            if "dnnList" not in upf:
                                upf["dnnList"] = []
                            for dnn in dnnList:
                                if dnn not in upf["dnnList"]:
                                    upf["dnnList"].append(dnn)
                            break

    def add_tac_conf(self, msg: dict) -> list:
        res = []
        smfName = self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["smfName"]
        sliceList = []
        if 'areas' in msg:
            for area in msg['areas']:
                # add specific slices
                if "slices" in area:
                    for slice in area["slices"]:
                        dnnList = self.get_dnn_list_from_net_names(self.conf,
                                        self.get_dnn_names_from_slice(self.conf, slice["sliceType"], slice["sliceId"]))
                        res += self.smf_add_upf(conf=self.conf, smfName=smfName, tac=area["id"],
                                    slice={"sst": SstConvertion.to_int(slice["sliceType"]),
                                           "sd": slice["sliceId"]}, dnnInfoList=dnnList)

                        # search slice to add area info. So every slice has all areas info
                        sdSstDnnlist = [{"sd": s["sd"], "sst": s["sst"]} for s in sliceList]
                        sliceToSearch = {"sd": slice["sliceId"], "sst": SstConvertion.to_int(slice["sliceType"])}
                        if sliceToSearch in sdSstDnnlist:
                            elem = sdSstDnnlist[sdSstDnnlist.index(sliceToSearch)]
                            if "tacList" in elem:
                                if {"id": area["id"]} not in elem["tacList"]:
                                    elem["tacList"].append({"id": area["id"]})
                            else:
                                elem["tacList"] = [{"id": area["id"]}]
                        else:
                            newSlice = {"sd": slice["sliceId"], "sst": SstConvertion.to_int(slice["sliceType"]),
                                        "tacList": [{"id": area["id"]}]}
                            sliceList.append(newSlice)

        # if sliceList:
        #     message = {"config": {"slices": sliceList}}
        #     self.add_slice(message)

        return res

    def del_tac_conf(self, msg: dict) -> list:
        res = []
        sliceList = []
        if 'areas' in msg:
            for area in msg['areas']:
                res += self.smf_del_upf(conf=msg, tac=area["id"])
        #         if "slices" in area:
        #             for slice in area["slices"]:
        #                 slice["tacList"] = [{"id": area["id"]}]
        #                 sliceList.append(slice)
        # if sliceList != []:
        #     message = {"config": {"slices": sliceList}}
        #     self.del_slice(message)
        #self.del_slice(msg)

        return res

    def checkSliceAndDnnInsideUpfNodes(self, sd: str = None , sst: int = None, dnns: List[str] = None) -> bool:
        """
        It checks if an UPF with this Slice and DNN inside node list of smf-configmap
        @param sd: 
        @param sst: 
        @param dnns: 
        @return: 
        """"""
        @param sd: 
        @param sst: 
        @param dnns: 
        @return: 
        """
        if not sd or not sst or not dnns:
            raise ValueError("sd ({}) and/or sst ({}) and/or dnn ({}) is None".format(sd, sst, dnns))
        # define model
        class SNssai(BaseModel):
            sd: str
            sst: int

        class Cidr(BaseModel):
            cidr: str

        class Dnn(BaseModel):
            dnn: str
            pools: List[Cidr] = None

        class SNssaiUpfInfo(BaseModel):
            dnnUpfInfoList: List[Dnn]
            sNssai: SNssai


        class UpfNodeInterface(BaseModel):
            endpoints: List[str]
            interfaceType: str
            networkInstance: str


        class UpfNode(BaseModel):
            interfaces: List[UpfNodeInterface]
            nodeID: str
            sNssaiUpfInfos: List[SNssaiUpfInfo]
            type: str

        class GnbNode(BaseModel):
            an_ip: str
            type: str

        upNodes = parse_obj_as(Dict[str, Union[UpfNode, GnbNode]], self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"] \
            ["userplaneInformation"]["upNodes"])

        for value in upNodes.values():
            if value.type == "UPF":
                for nssaiInfo in value.sNssaiUpfInfos:
                    if nssaiInfo.sNssai.sd == sd and nssaiInfo.sNssai.sst == sst:
                        for upfInfo in nssaiInfo.dnnUpfInfoList:
                            if upfInfo.dnn in dnns and upfInfo.pools:
                                return True
        return False

    def add_slice(self, msg: dict) -> list:
        if msg is None:
            logger.warn("Conf is None")
            return []

        if "config" in msg and "plmn" in msg['config']:
            mcc = msg['config']['plmn'][:3]
            mnc = msg['config']['plmn'][3:]
        else:
            raise ValueError("config section is not in conf or plmn not specified in config section")

        res = []
        tacList = []
        sliceList = []
        dnnList = []

        amfId = self.running_free5gc_conf["free5gc-amf"]["amf"]["configuration"]["configurationBase"] \
            ["servedGuamiList"][0]["amfId"]
        smfName= self.running_free5gc_conf["free5gc-smf"]["smf"]["configuration"]["configurationBase"]["smfName"]
        n3iwfId = self.running_free5gc_conf["free5gc-n3iwf"]["n3iwf"]["configuration"]["configurationBase"] \
            ["N3IWFInformation"]["GlobalN3IWFID"]["N3IWFID"]
        nssfName = self.running_free5gc_conf["free5gc-nssf"]["nssf"]["configuration"]["configurationBase"]["nssfName"]

        if "areas" in msg:
            for area in msg["areas"]:
                if "slices" in area:
                    for extSlice in area["slices"]:
                        dnnSliceList = []
                        slice = {"sd": extSlice["sliceId"], "sst": SstConvertion.to_int(extSlice["sliceType"])}
                        sliceList.append(slice)
                        dnnNames = self.get_dnn_names_from_slice(self.conf, extSlice["sliceType"], extSlice["sliceId"])
                        # addPool specify if add pools data or not. It is the reverse of "exist question". Add only if not exists
                        addPool = not(self.checkSliceAndDnnInsideUpfNodes(slice["sd"], slice["sst"], dnnNames))
                        extDnnList=self.get_dnn_list_from_net_names(self.conf, dnnNames, addPool)
                        dnnSliceList.extend(extDnnList)
                        dnnList.extend(extDnnList)

                        self.smf_set_configuration(mcc=mcc, mnc=mnc, smfName=smfName, dnnList=dnnSliceList,
                                                   sliceList=[slice])

                        # add DNNs to upf configuration
                        # if len(dnnSliceList) != 0:
                        #     for upf in self.conf["config"]["upf_nodes"]:
                        #         if upf["area"] == area["id"]:
                        #             if "dnnList" in upf:
                        #                 upf["dnnList"].extend(dnnSliceList)
                        #             else:
                        #                 upf["dnnList"] = copy.deepcopy(dnnSliceList)
                        #             break

                        tacList.append(area["id"])
                        self.n3iwf_set_configuration(mcc=mcc, mnc= mnc, n3iwfId=n3iwfId, tac=area["id"],
                                sliceSupportList=[slice])
                        self.nssf_set_configuration(mcc=mcc, mnc=mnc, nssfName=nssfName, sliceList=[slice],
                                tac=area["id"])
                        res += self.smf_add_upf(conf=self.conf, smfName=smfName, tac=area["id"], slice=slice,
                                dnnInfoList=self.get_dnn_list_from_net_names(self.conf, dnnNames, addPool))
                    self.amf_set_configuration(mcc=mcc, mnc=mnc, amfId=amfId, supportedTacList = tacList,
                                snssaiList = sliceList, dnnList = dnnList)

        return res

    def del_slice(self, msgModel) -> None:
        if type(msgModel) is dict:
            msg = msgModel
        else:
            msg = msgModel.dict()

        if msg is None:
            logger.warn("Conf is None")
            return

        if "config" in msg and "plmn" in msg['config']:
            mcc = msg['config']['plmn'][:3]
            mnc = msg['config']['plmn'][3:]
        else:
            raise ValueError("config section is not in conf or plmn not specified in config section")

        if "areas" in msg:
            for area in msg["areas"]:
                if "slices" in area:
                    for extSlice in area["slices"]:
                        dnnSliceList = []
                        sliceList = [{"sd": extSlice["sliceId"], "sst": SstConvertion.to_int(extSlice["sliceType"])}]
                        if "dnnList" in extSlice:
                            dnnSliceList.extend(self.get_dnn_list_from_net_names(self.conf,
                                    self.get_dnn_names_from_slice(self.conf, extSlice["sliceType"], extSlice["sliceId"])))
                        self.amf_unset_configuration(mcc=mcc, mnc=mnc, snssaiList=sliceList,dnnList=dnnSliceList)
                        self.smf_unset_configuration(dnnList=dnnSliceList, sliceList=sliceList)
                        self.n3iwf_unset_configuration(sliceSupportList=sliceList)
                        self.nssf_unset_configuration(sliceList=sliceList)

                    # self.config_5g_core_for_reboot()
                    #
                    # msg2up = {'config': self.running_free5gc_conf}
                    # res += self.core_upXade(msg2up) + tail_res


    def getConfiguration(self) -> dict:
        return self.running_free5gc_conf
