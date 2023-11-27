import importlib
from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from blueprints.blue_5g_base.models import Create5gModel
from blueprints.blueprint_beta import BlueprintBaseBeta
from models.base_model import NFVCLBaseModel
from models.blueprint.blueprint_base_model import BlueNSD, BlueVNFD
from models.network import PduModel
from models.vim.vim_models import VimNetMap, VirtualNetworkFunctionDescriptor, PhysicalDeploymentUnit, VimModel
from nfvo import get_ns_vld_ip
from nfvo.nsd_manager_beta import Sol006NSDBuilderBeta
from nfvo.vnf_manager_beta import Sol006VnfdBuilderBeta
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


class Networks5G(NFVCLBaseModel):
    wan: str
    mgt: str


class Blue5GBaseBeta(BlueprintBaseBeta, ABC):
    blue_model_5g: Create5gModel
    core_vim: VimModel
    networks_5g: Networks5G
    core_area_id: int

    nsd_core: BlueNSD
    nsd_ran: BlueNSD

    # TODO get these from the VMs, maybe using the CIDR of their network
    MGT_NETWORK_IF_NAME = "ens3"
    WAN_NETWORK_IF_NAME = "ens4"

    # TODO need to be moved
    nb_mgt_ip: str
    nb_wan_ip: str
    amf_ip: str

    def init_base(self):
        logger.debug("init_base")
        core_areas = list(filter(lambda x: x.core, self.blue_model_5g.areas))
        if len(core_areas) == 1:
            self.core_area_id = core_areas[0].id
        else:
            # TODO is this correct?
            raise ValueError("Only one area is allowed for core")
        self.core_vim = self.get_topology().get_vim_from_area_id_model(self.core_area_id)
        self.check_and_set_networks()

    def check_and_set_networks(self):
        if self.blue_model_5g.config.network_endpoints.wan in self.core_vim.networks:
            wan_network = self.blue_model_5g.config.network_endpoints.wan
        else:
            raise ValueError(f"Network {self.blue_model_5g.config.network_endpoints.wan} not found in VIM")

        if self.blue_model_5g.config.network_endpoints.mgt in self.core_vim.networks:
            mgt_network = self.blue_model_5g.config.network_endpoints.mgt
        else:
            raise ValueError(f"Network {self.blue_model_5g.config.network_endpoints.mgt} not found in VIM")
        self.networks_5g = Networks5G(wan=wan_network, mgt=mgt_network)

    def nsd(self) -> List[str]:
        nsd_list: List[str] = self.core_nsd()
        nsd_list.extend(self.edge_nsd())
        # nsd_list.extend(self.ran_nsd())
        logger.info("Blue {} - created NSDs: {}".format(self.get_id(), nsd_list))
        return nsd_list

    @abstractmethod
    def core_vnfd(self, vls: List[VimNetMap]) -> List[BlueVNFD]:
        pass

    @abstractmethod
    def edge_vnfd(self, vls: List[VimNetMap]) -> List[BlueVNFD]:
        pass

    def ran_vnfd(self, pdu: PduModel = None) -> List[BlueVNFD]:
        logger.debug("Blue {} - setting VNFd for RAN")

        created_pdu = PhysicalDeploymentUnit.build_pdu(1, pdu.name, pdu.interface)

        ran_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            str(self.get_id()) + '_' + pdu.implementation + "_tac" + '_enb',
            pdu_list=[created_pdu]
        )
        built_ran_vnfd_package = Sol006VnfdBuilderBeta(ran_vnfd, hemlflexcharm=True)
        blue_vnfd = built_ran_vnfd_package.get_vnf_blue_descr_only_pdu()
        self.base_model.vnfd.area.append(blue_vnfd)
        self.to_db()
        return [blue_vnfd]

    @abstractmethod
    def core_nsd(self) -> List[str]:
        pass

    @abstractmethod
    def edge_nsd(self) -> List[str]:
        pass

    def ran_nsd(self) -> List[str]:
        logger.info("Blue {} - Creating RAN NSD(s) for area")
        # TODO fix area id
        pdu = self.topology_get_pdu_by_area_and_type(0, 'nb')

        if pdu is None:
            raise ValueError('pdu not found for tac ' + str(0))
        logger.info("Blue {} - for area {} pdu {} ({}) selected".format(self.get_id(), 0, pdu.name, pdu.implementation))

        # TODO fix hardcored
        mgt_network = "dmz-internal"
        wan_network = "alderico-net"

        # wan_network = self.blue_sdcore_model.config["network_endpoints"]["wan"]
        # mgt_network = self.blue_sdcore_model.config["network_endpoints"]["mgt"]

        vim_net_mapping = [
            VimNetMap.build_vnm(
                "mgt",
                "ens3",
                mgt_network,
                True,
                "mgt_net"
            ),
            VimNetMap.build_vnm(
                "datanet",
                "ens4",
                wan_network,
                False,
                "data_net"
            )
        ]

        blue_vnfd_list = self.ran_vnfd(pdu)
        core_vim: VimModel = self.get_topology().get_vim_from_area_id_model(0)

        nsd_id = '{}_NGRAN_{}'.format(self.get_id(), 0)

        n_obj = Sol006NSDBuilderBeta(
            blue_vnfd_list,
            core_vim.name,
            nsd_id,
            "ran",
            vim_net_mapping,
        )

        nsd_item = n_obj.get_nsd()
        nsd_item.area_id = 0
        nsd_item.vld = pdu.interface

        self.base_model.nsd_.append(nsd_item)
        self.nsd_ran = nsd_item
        self.to_db()
        return [nsd_id]

    def kdu_upgrade(self, nsd: BlueNSD, conf_params: dict, kdu_name, vnf_id="1"):
        # TODO make a Pydantic model for this
        res = [
            {
                # TODO find a better way to get nsd name
                'ns-name': nsd.descr.nsd.nsd[0].name,
                'nsi_id': nsd.nsi_id,
                'primitive_data': {
                    'member_vnf_index': vnf_id,
                    'kdu_name': kdu_name,
                    'primitive': 'upgrade',
                    'primitive_params': conf_params
                }
            }
        ]
        return res

    @abstractmethod
    def core_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        pass

    @abstractmethod
    def edge_day2_conf(self, arg: dict, nsd_item: dict) -> List[str]:
        pass

    def ran_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        logger.info("Blue {} - Initializing RAN Day2 configurations".format(self.get_id()))
        # here we have to find the correct enb_configurator
        res = []

        # TODO get area from config
        vim: VimModel = self.get_topology().get_vim_from_area_id_model(0)
        pdu_item = self.topology_get_pdu_by_area_and_type(0, 'nb')

        # allocating the correct configurator obj for the pnf
        nb_configurator = self.db.findone_DB('pnf', {'type': pdu_item['implementation']})
        module = importlib.import_module(nb_configurator['module'])
        Configurator_NB = getattr(module, nb_configurator['name'])

        if len(nsd_item['vld']) > 1:
            # TODO è giusto "data"?
            wan_vld = next((item for item in nsd_item['vld'] if item['vld'] == 'data'), None)
            if wan_vld is None:
                raise ValueError('wan  vld not found')
        else:
            # this is for pnf with only 1 interface
            wan_vld = nsd_item['vld'][0]

        conf_data = {
            # TODO prendere da config
            'plmn': "20893",
            'tac': nsd_item['area'],
            'gtp_ip': self.nb_wan_ip,
            # 'mme_ip': self.conf['config']['core_wan_ip'],
            'wan_nic_name': wan_vld['name'],
        }

        conf_data['amf_ip'] = self.amf_ip

        # add already enabled slices to the ran
        # TODO fix
        # if 'slices' in area:
        #     conf_data['nssai'] = [NssiConvertion.toNssi(i) for i in area['slices']]

        # override gnb settings from arg
        # TODO fix
        # if 'nb_config' in self.conf:
        #     conf_data['nb_config'] = self.conf['nb_config']
        # if 'tunnel' in self.conf:
        #     conf_data['tunnel'] = self.conf['tunnel']

        conf_obj = Configurator_NB(
            '{}_NGRAN_{}'.format(self.get_id(), nsd_item['area']),
            1,
            self.get_id(),
            conf_data,
            self.topology_get_pdu_by_area(nsd_item['area'])
        )
        # TODO a cosa serve?
        # self.vnf_configurator.append(conf_obj)
        res += conf_obj.dump()
        logger.info("e/gNB configuration built for tac " + str(nsd_item['area']))
        return res

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

    def get_ip_ran(self, ns: BlueNSD) -> None:
        # TODO fix hardcoded network name
        vlds = get_ns_vld_ip(ns.nsi_id, ["mgt", f'datanet'])
        self.nb_wan_ip = vlds["datanet"][0]['ip']
        self.nb_mgt_ip = vlds["mgt"][0]['ip']

        logger.debug(f'MGT IP for ran: {self.nb_wan_ip}')
        logger.debug(f'DATA IP for ran: {self.nb_mgt_ip}')

    def get_ip(self) -> None:
        logger.info('Blue {} - Getting IP addresses of VNF instances'.format(self.get_id()))
        for n in self.base_model.nsd_:
            # TODO fix hardcoded nsd types
            if n.type == 'core':
                self.get_ip_core(n)
            if n.type == 'edge':
                self.get_ip_edge(n)
            if n.type == 'ran':
                self.get_ip_ran(n)
        self.to_db()

    @abstractmethod
    def _destroy(self):
        pass
