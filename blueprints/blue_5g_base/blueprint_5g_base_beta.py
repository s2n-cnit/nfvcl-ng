import importlib
from enum import Enum
from typing import List, Optional
from abc import ABC, abstractmethod
from blueprints import BlueprintBase
from blueprints.blueprint_beta import BlueprintBaseBeta
from models.blueprint.blueprint_base_model import BlueNSD, BlueVNFD
from models.vim.vim_models import VimNetMap
from nfvo import sol006_NSD_builder, sol006_VNFbuilder, get_ns_vld_ip
from utils.log import create_logger

# create logger
logger = create_logger('Abstract5GBlueBeta')


class SstConvertion():
    sstType = {"EMBB": 1, "URLLC": 2, "MMTC": 3}

    def __init__(self) -> None:
        pass

    @classmethod
    def to_string(cls, value: int = None) -> str:
        return next((k for k, v in cls.sstType.items() if v == value), None)

    @classmethod
    def to_int(cls, value: str = None) -> int:
        return next((v for k, v in cls.sstType.items() if k == value), None)


class NssiConvertion(SstConvertion):
    @classmethod
    def toNssi(cls, fromSlice: dict = None):
        return {"sst": cls.to_int(fromSlice["sliceType"]), "sd": fromSlice["sliceId"]}

    @classmethod
    def toSlice(cls, fromNssi: dict = None):
        return {"sliceType": cls.to_string(fromNssi["sst"]), "sliceId": fromNssi["sd"]}


class Area5GEnum(Enum):
    CORE = "core"
    AREA = "area"


class Blue5GBaseBeta(BlueprintBaseBeta, ABC):

    def nsd(self) -> List[str]:
        nsd_list: List[str] = self.core_nsd()
        nsd_list.extend(self.edge_nsd())
        logger.info("Blue {} - created NSDs: {}".format(self.get_id(), nsd_list))
        return nsd_list

    @abstractmethod
    def core_vnfd(self, vls: List[VimNetMap]) -> List[BlueVNFD]:
        pass

    @abstractmethod
    def edge_vnfd(self, vls: List[VimNetMap]) -> List[BlueVNFD]:
        pass

    @abstractmethod
    def core_nsd(self) -> List[str]:
        pass

    @abstractmethod
    def edge_nsd(self) -> List[str]:
        pass

    @abstractmethod
    def core_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        pass

    @abstractmethod
    def edge_day2_conf(self, arg: dict, nsd_item: dict) -> List[str]:
        pass

    # def init_day2_conf(self, msg: dict) -> list:
    #     logger.debug("Blue {} - Initializing Day2 configurations".format(self.get_id()))
    #     res = []
    #     tail_res = []
    #
    #     for n in self.nsd_:
    #         if n['type'] == 'core':
    #             logger.debug("Blue {} - running core Day2 configurations".format(self.get_id()))
    #             res += self.core_day2_conf(msg, n)
    #         elif n['type'] == 'edge':
    #             logger.debug("Blue {} - running edge Day2 configurations".format(self.get_id()))
    #             res += self.edge_day2_conf(msg, n)
    #         elif n['type'] == 'ran':
    #             logger.debug("Blue {} - running ran Day2 configurations".format(self.get_id()))
    #             res += self.ran_day2_conf(msg, n)
    #
    #     self.add_ues(msg)
    #
    #     return res

    @abstractmethod
    def add_ues(self, msg: dict):
        pass

    @abstractmethod
    def get_ip_core(self, ns: BlueNSD) -> None:
        pass

    @abstractmethod
    def get_ip_edge(self, ns: BlueNSD) -> None:
        pass

    def get_ip(self) -> None:
        logger.info('Blue {} - Getting IP addresses of VNF instances'.format(self.get_id()))
        for n in self.base_model.nsd_:
            if n.type == 'core':
                self.get_ip_core(n)
            if n.type == 'edge':
                self.get_ip_edge(n)
        self.to_db()

    @abstractmethod
    def _destroy(self):
        pass
