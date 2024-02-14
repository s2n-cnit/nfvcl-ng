import importlib
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Dict, Union

from pydantic import Field

from blueprints.blue_5g_base.models import Create5gModel
from blueprints.blue_5g_base.models.blue_5g_model import SubArea, SubSlices, SubAreaOnlyId
from blueprints.blueprint_beta import BlueprintBaseBeta
from models.base_model import NFVCLBaseModel
from models.blueprint.blueprint_base_model import BlueNSD, BlueVNFD, BlueprintBaseModel
from models.network import PduModel
from models.vim.vim_models import VimNetMap, VirtualNetworkFunctionDescriptor, PhysicalDeploymentUnit, VimModel
from nfvo import get_ns_vld_ip, NbiUtil
from nfvo.nsd_manager_beta import Sol006NSDBuilderBeta, get_ns_vld_model
from nfvo.vnf_manager_beta import Sol006VnfdBuilderBeta
from utils.log import create_logger
from utils.persistency import DB

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
    def toNssi(cls, fromSlice: SubSlices = None):
        return {"sst": cls.to_int(fromSlice.sliceType), "sd": fromSlice.sliceId}

    @classmethod
    def toSlice(cls, fromNssi: dict = None) -> SubSlices:
        return SubSlices.model_validate({"sliceType": cls.to_string(fromNssi["sst"]), "sliceId": fromNssi["sd"]})  # TODO workaround for Literal type


class Area5GTypeEnum(Enum):
    CORE = "core"
    EDGE = "edge"
    RAN = "ran"


class Area5G(NFVCLBaseModel):
    """
    Base class that define an Area for 5G blueprints
    """
    id: int
    type: Area5GTypeEnum
    nsd: Optional[BlueNSD] = Field(default=None)


class CoreArea5G(Area5G):
    """
    Class that define a core area for 5G blueprints

    amf_ip: IP address of the amf core function, needs to be reachable by the gnb
    """
    type: Area5GTypeEnum = Area5GTypeEnum.CORE
    amf_ip: Optional[str] = Field(default=None)


class EdgeArea5G(Area5G):
    """
    Class that define a edge area for 5G blueprints

    upf_mgt_ip: IP address of the mgt interface of the UPF vm in this area
    upf_data_ip: IP address of the data interface of the UPF vm in this area
    upf_data_network_cidr: CIDR of the data network
    upf_ue_ip_pool: Pool of IP to use for UEs connecting to this area
    """
    type: Area5GTypeEnum = Area5GTypeEnum.EDGE
    upf_mgt_ip: Optional[str] = Field(default=None)
    upf_data_ip: Optional[str] = Field(default=None)
    upf_data_network_cidr: Optional[str] = Field(default=None)
    upf_ue_ip_pool: Optional[str] = Field(default=None)
    upf_dnn: Optional[str] = Field(default=None)


class RanArea5G(Area5G):
    """
    Class that define a edge area for 5G blueprints

    nb_mgt_ip: IP address of the mgt interface of the GNB vm in this area
    nb_wan_ip: IP address of the data interface of the GNB vm in this area
    """
    type: Area5GTypeEnum = Area5GTypeEnum.RAN
    nb_mgt_ip: Optional[str] = Field(default=None)
    nb_wan_ip: Optional[str] = Field(default=None)


class Networks5G(NFVCLBaseModel):
    wan: str
    mgt: str


class Blueprint5GBaseModel(BlueprintBaseModel):
    """
    Class that contains additional blueprint data that need to be saved in NFVCL's database
    """
    blue_model_5g: Optional[Create5gModel] = Field(default=None)
    core_vim: Optional[VimModel] = Field(default=None)
    networks_5g: Optional[Networks5G] = Field(default=None)
    core_area: Optional[CoreArea5G] = Field(default=None)
    edge_areas: Dict[int, EdgeArea5G] = {}
    ran_areas: Dict[int, RanArea5G] = {}


class Blue5GBaseBeta(BlueprintBaseBeta, ABC):
    # TODO get these from the VMs, maybe using the CIDR of their network
    MGT_NETWORK_IF_NAME = "ens3"
    WAN_NETWORK_IF_NAME = "ens4"

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None, db: DB = None, nbiutil: NbiUtil = None):
        super().__init__(conf, id_, data, db, nbiutil)
        # This convert the base_model to the Blueprint5GBaseModel, it is necessary to store more data in the persistence layer
        self.base_model: Blueprint5GBaseModel = Blueprint5GBaseModel.model_validate(self.base_model.model_dump())

    def init_base(self):
        """
        Initialize areas and networks
        """

        logger.debug("init_base")
        core_areas = list(filter(lambda x: x.core, self.base_model.blue_model_5g.areas))
        non_core_areas = list(filter(lambda x: not x.core, self.base_model.blue_model_5g.areas))

        if len(core_areas) == 1:
            self.base_model.core_area = CoreArea5G(id=core_areas[0].id)
            self.base_model.edge_areas[core_areas[0].id] = EdgeArea5G(id=core_areas[0].id)
            self.base_model.ran_areas[core_areas[0].id] = RanArea5G(id=core_areas[0].id)
        else:
            # TODO is this correct?
            raise ValueError("Only one area is allowed for core")

        for non_core_area in non_core_areas:
            self.base_model.edge_areas[non_core_area.id] = EdgeArea5G(id=non_core_area.id)
            self.base_model.ran_areas[non_core_area.id] = RanArea5G(id=non_core_area.id)

        self.base_model.core_vim = self.get_topology().get_vim_from_area_id_model(self.base_model.core_area.id)
        self.check_and_set_networks()

    def check_and_set_networks(self):
        """
        Check if the networks present in the config exists inside the topology
        If a network does not exist raise an exception, if everything is ok a reference to the networks is saved in self.base_model.networks_5g
        """
        if self.base_model.blue_model_5g.config.network_endpoints.wan in self.base_model.core_vim.networks:
            wan_network = self.base_model.blue_model_5g.config.network_endpoints.wan
        else:
            raise ValueError(f"Network {self.base_model.blue_model_5g.config.network_endpoints.wan} not found in VIM")

        if self.base_model.blue_model_5g.config.network_endpoints.mgt in self.base_model.core_vim.networks:
            mgt_network = self.base_model.blue_model_5g.config.network_endpoints.mgt
        else:
            raise ValueError(f"Network {self.base_model.blue_model_5g.config.network_endpoints.mgt} not found in VIM")
        self.base_model.networks_5g = Networks5G(wan=wan_network, mgt=mgt_network)

    def nsd(self) -> List[str]:
        nsd_list: List[str] = []

        # Core area NSDs
        nsd_list.extend(self.core_nsd(self.base_model.core_area))

        # Edge areas NSDs
        for edge_area in self.base_model.edge_areas.values():
            nsd_list.extend(self.edge_nsd(edge_area))

        # Ran areas NSDs
        for ran_area in self.base_model.ran_areas.values():
            nsd_list.extend(self.ran_nsd(ran_area))

        logger.info("Blue {} - created NSDs: {}".format(self.get_id(), nsd_list))
        return nsd_list

    @abstractmethod
    def core_vnfd(self, area: CoreArea5G, vls: List[VimNetMap]) -> List[BlueVNFD]:
        pass

    @abstractmethod
    def edge_vnfd(self, area: EdgeArea5G, vls: List[VimNetMap]) -> List[BlueVNFD]:
        pass

    def ran_vnfd(self, area: RanArea5G, pdu: PduModel) -> List[BlueVNFD]:
        logger.debug(f"Blue {self.get_id()} - setting VNFd for RAN area {area.id}")

        created_pdu = PhysicalDeploymentUnit.build_pdu(1, pdu.name, pdu.interface)

        ran_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            f"{self.get_id()}_{pdu.implementation}_tac{area.id}_enb_pnfd",
            pdu_list=[created_pdu]
        )
        built_ran_vnfd_package = Sol006VnfdBuilderBeta(ran_vnfd, hemlflexcharm=True)
        blue_vnfd = built_ran_vnfd_package.get_vnf_blue_descr_only_pdu()
        blue_vnfd.area_id = area.id
        self.base_model.vnfd.area.append(blue_vnfd)
        self.to_db()
        return [blue_vnfd]

    @abstractmethod
    def core_nsd(self, area: CoreArea5G) -> List[str]:
        pass

    @abstractmethod
    def edge_nsd(self, area: EdgeArea5G) -> List[str]:
        pass

    def ran_nsd(self, area: RanArea5G) -> List[str]:
        logger.info(f"Blue {self.get_id()} - Creating RAN NSD(s) for area {area.id}")
        pdu = self.topology_get_pdu_by_area_and_type(area.id, 'nb')
        vim = self.get_topology().get_vim_from_area_id_model(area.id)

        if pdu is None:
            raise ValueError('pdu not found for tac ' + str(0))
        logger.info("Blue {} - for area {} pdu {} ({}) selected".format(self.get_id(), area.id, pdu.name, pdu.implementation))

        vim_net_mapping = [
            VimNetMap.build_vnm(
                "mgt",
                self.MGT_NETWORK_IF_NAME,
                self.base_model.networks_5g.mgt,
                True,
                "mgt_net"
            ),
            VimNetMap.build_vnm(
                "datanet",
                self.WAN_NETWORK_IF_NAME,
                self.base_model.networks_5g.wan,
                False,
                "data_net"
            )
        ]

        blue_vnfd_list = self.ran_vnfd(area, pdu)

        nsd_id = '{}_NGRAN_{}'.format(self.get_id(), area.id)

        n_obj = Sol006NSDBuilderBeta(
            blue_vnfd_list,
            vim.name,
            nsd_id,
            Area5GTypeEnum.RAN.value,
            vim_net_mapping,
        )

        nsd_item = n_obj.get_nsd()
        nsd_item.area_id = area.id
        nsd_item.vld = pdu.interface
        self.base_model.nsd_.append(nsd_item)
        area.nsd = nsd_item
        self.to_db()
        return [nsd_id]

    def kdu_upgrade(self, nsd: BlueNSD, conf_params: dict, kdu_name, vnf_id="1"):
        """
        Send updated configuration to a KDU
        This is similar to running `helm upgrade` after editing `values.yaml`
        """
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
    def core_day2_conf(self, area: CoreArea5G) -> list:
        pass

    @abstractmethod
    def edge_day2_conf(self, area: EdgeArea5G) -> List[str]:
        pass

    @abstractmethod
    def get_additional_ran_conf(self, area: RanArea5G) -> dict:
        pass

    def ran_day2_conf(self, area: RanArea5G) -> list:
        res = []
        logger.info(f"Blue {self.get_id()} - Initializing RAN Day2 configurations for area {area.id}")
        # here we have to find the correct enb_configurator
        nsd_item = area.nsd

        pdu_item = self.topology_get_pdu_by_area_and_type(area.id, 'nb')

        # allocating the correct configurator obj for the pnf
        nb_configurator = self.db.findone_DB('pnf', {'type': pdu_item.implementation})
        module = importlib.import_module(nb_configurator['module'])
        Configurator_NB = getattr(module, nb_configurator['name'])

        # TODO rewrite
        if len(nsd_item.vld) > 1:
            # TODO what is `datanet`?
            wan_vld = next((item for item in nsd_item.vld if item.vld == 'datanet'), None)
            if wan_vld is None:
                raise ValueError('wan  vld not found')
        else:
            # this is for pnf with only 1 interface
            wan_vld = nsd_item.vld[0]

        conf_data = {
            'plmn': self.base_model.blue_model_5g.config.plmn,
            'tac': nsd_item.area_id,
            'gtp_ip': area.nb_wan_ip,
            'wan_nic_name': wan_vld.name,
            'amf_ip': self.base_model.core_area.amf_ip
        }

        # Merge dictionaries
        conf_data = conf_data | self.get_additional_ran_conf(area)

        # add already enabled slices to the ran
        slices = next(filter(lambda x: x.id == area.id, self.base_model.blue_model_5g.areas)).slices
        if slices:
            conf_data['nssai'] = [NssiConvertion.toNssi(i) for i in slices]

        # override gnb settings from arg
        # TODO fix
        # if 'nb_config' in self.blue_model_5g.:
        #     conf_data['nb_config'] = self.conf['nb_config']
        # if 'tunnel' in self.conf:
        #     conf_data['tunnel'] = self.conf['tunnel']

        conf_obj = Configurator_NB(
            f'{self.get_id()}_NGRAN_{nsd_item.area_id}',
            1,
            self.get_id(),
            conf_data,
            self.topology_get_pdu_by_area(nsd_item.area_id).model_dump(exclude_none=True)
        )
        res += conf_obj.dump()
        logger.info("e/gNB configuration built for tac " + str(nsd_item.area_id))
        return res

    def init_day2_conf(self, msg) -> list:
        """
        Create day2 configuration for every area of every type
        """

        logger.info("Initializing Day2 configurations")
        res = []
        logger.info(f"Initializing Day2 configuration for core area {self.base_model.core_area.id}")
        res += self.core_day2_conf(self.base_model.core_area)
        for edge_area in self.base_model.edge_areas.values():
            logger.info(f"Initializing Day2 configuration for edge area {edge_area.id}")
            res += self.edge_day2_conf(edge_area)
        for ran_area in self.base_model.ran_areas.values():
            logger.info(f"Initializing Day2 configuration for ran area {ran_area.id}")
            res += self.ran_day2_conf(ran_area)
        return res

    def add_tac(self, area: SubArea):
        """
        Add a tac to the blueprint
        Args:
            area: Area to add tac to
        """
        logger.info("Add TAC Day0")

        nsd_list: List[str] = []

        for already_existing_area in self.base_model.blue_model_5g.areas:
            if already_existing_area.id == area.id:
                raise ValueError("An area with this id is already present")
        self.base_model.blue_model_5g.areas.append(area)
        self.base_model.edge_areas[area.id] = EdgeArea5G(id=area.id)
        self.base_model.ran_areas[area.id] = RanArea5G(id=area.id)

        nsd_list.extend(self.edge_nsd(self.base_model.edge_areas[area.id]))
        nsd_list.extend(self.ran_nsd(self.base_model.ran_areas[area.id]))

        return nsd_list

    def add_tac_day2(self, area: SubArea):
        logger.info("Add TAC Day2 configurations")
        edge_area: EdgeArea5G = self.base_model.edge_areas[area.id]
        ran_area: RanArea5G = self.base_model.ran_areas[area.id]
        self.get_ip_edge(edge_area.nsd)
        self.get_ip_ran(ran_area.nsd)
        res = []
        res += self.edge_day2_conf(edge_area)
        res += self.ran_day2_conf(ran_area)
        return res

    def del_tac(self, area: SubAreaOnlyId):
        nsd_list: List[str] = [
            self.base_model.edge_areas[area.id].nsd.nsi_id,
            self.base_model.ran_areas[area.id].nsd.nsi_id
        ]
        return nsd_list

    def del_tac_callback(self, callback_msg: list):
        logger.debug("Del tac callback")

        edge_to_be_deleted = []
        ran_to_be_deleted = []
        for edge_area in list(self.base_model.edge_areas.values()):
            if edge_area.nsd.nsi_id in callback_msg:
                edge_to_be_deleted.append(edge_area.id)

        for ran_area in list(self.base_model.ran_areas.values()):
            if ran_area.nsd.nsi_id in callback_msg:
                ran_to_be_deleted.append(ran_area.id)

        for ed in edge_to_be_deleted:
            del self.base_model.edge_areas[ed]

        for ra in ran_to_be_deleted:
            del self.base_model.ran_areas[ra]

        for area in self.base_model.blue_model_5g.areas.copy():
            if area.id in edge_to_be_deleted or area.id in ran_to_be_deleted:
                self.base_model.blue_model_5g.areas.remove(area)

    def del_tac_day2(self, area: SubArea):
        """
        Override this method to perform day2 operations on the core when a tac area is deleted
        """
        return []

    @abstractmethod
    def get_ip_core(self, ns: BlueNSD) -> None:
        pass

    @abstractmethod
    def get_ip_edge(self, ns: BlueNSD) -> None:
        pass

    def get_ip_ran(self, ns: BlueNSD) -> None:
        logger.debug(f'Getting IPs for ran area {ns.area_id}')

        vlds = get_ns_vld_model(ns.nsi_id, ["mgt", "datanet"])
        self.base_model.ran_areas[ns.area_id].nb_mgt_ip = vlds["mgt"][0].get_ip_list_str()[0]
        self.base_model.ran_areas[ns.area_id].nb_wan_ip = vlds["datanet"][0].get_ip_list_str()[0] # vld is called datanet from ueransim blueprint

        logger.debug(f'MGT IP for ran area {ns.area_id}: {self.base_model.ran_areas[ns.area_id].nb_mgt_ip}')
        logger.debug(f'DATA IP for ran area {ns.area_id}: {self.base_model.ran_areas[ns.area_id].nb_wan_ip}')

    def get_ip(self) -> None:
        logger.info('Blue {} - Getting IP addresses of VNF instances'.format(self.get_id()))
        for n in self.base_model.nsd_:
            if n.type == Area5GTypeEnum.CORE.value:
                self.get_ip_core(n)
            if n.type == Area5GTypeEnum.EDGE.value:
                self.get_ip_edge(n)
            if n.type == Area5GTypeEnum.RAN.value:
                self.get_ip_ran(n)
        self.to_db()

    @abstractmethod
    def _destroy(self):
        pass
