from ipaddress import IPv4Network, IPv4Address

from models.blueprint.rest_blue import BlueGetDataModel
from models.network import NetworkTypeEnum, NetworkModel
from models.network.network_models import IPv4Pool, PduInterface, PduModel
from models.ueransim.blueprint_ueransim_model import UeransimModel, UeransimArea, UeransimUe
from models.vim.vim_models import VimLink, VirtualNetworkFunctionDescriptor, VirtualDeploymentUnit, VMFlavors, VimNetMap
from nfvo.nsd_manager_beta import Sol006NSDBuilderBeta, get_ns_vld_model
from nfvo.vnf_manager_beta import Sol006VnfdBuilderBeta
from utils import persistency
from utils.log import create_logger
from typing import Union, Dict, List
from fastapi import status
from .configurators.ueransim_configurator_beta import ConfiguratorUeUeRanSimBeta
from nfvo.osm_nbi_util import get_osm_nbi_utils
from .models.blue_ueransim_model import UeranSimBlueprintRequestAddDelUe
from ..blueprint_beta import BlueprintBaseBeta

nbiUtil = get_osm_nbi_utils()
db = persistency.DB()
logger = create_logger('UeRanSim')


class UeRanSimBeta(BlueprintBaseBeta):

    uer_model: UeransimModel
    RADIO_NET_CIDR = '10.168.0.0/16'
    RADIO_NET_CIDR_START = '10.168.0.2'
    RADIO_NET_CIDR_END = '10.168.255.253'
    VM_IMAGE = 'ueransim_v2.1'
    UE_FLAVOR: VMFlavors = VMFlavors(vcpu_count='2', memory_mb='4096', storage_gb='8')
    GNB_FLAVOR: VMFlavors = VMFlavors(vcpu_count='2', memory_mb='4096', storage_gb='8')
    UE_NS_TYPE = 'ns'
    GNB_NS_TYPE = 'nb'
    DEFAULT_USER = 'root'
    DEFAULT_PASSWORD = 'ueransim'

    def pre_initialization_checks(self) -> bool:
        pass

    @classmethod
    def rest_create(cls, msg: UeransimModel):
        return cls.api_day0_function(msg)

    # Fixme: create the pydantic model for adding/removing UEs
    @classmethod
    def rest_add_ues(cls, msg: UeranSimBlueprintRequestAddDelUe, blue_id: str):
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def rest_del_ues(cls, msg: UeranSimBlueprintRequestAddDelUe, blue_id: str):
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def day2_methods(cls):
        cls.api_router.add_api_route("/{blue_id}/add_ues", cls.rest_add_ues, methods=["PUT"])
        cls.api_router.add_api_route("/{blue_id}/del_ues", cls.rest_del_ues, methods=["DEL"])


    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None):
        """
        Initialize the model
        Args:
            conf:
            id_:
            data:
        """
        BlueprintBaseBeta.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
        logger.info("Creating UeRanSim Blueprint")
        self.base_model.supported_operations = {
            'init': [{'day0': [{'method': 'bootstrap_day0'}], 'day2': [{'method': 'init_day2_conf'}], 'dayN': []}],
            'add_ue': [{'day0': [{'method': 'add_ue'}], 'day2': [{'method': 'add_ue_day2'}], 'dayN': []}],
            'del_ue': [{'day0': [], 'day2': [{'method': 'del_ue'}], 'dayN': []}],
            'add_nb': [{'day0': [{'method': 'add_ue'}], 'day2': [{'method': 'add_ue_day2'}], 'dayN': []}],
            'del_nb': [{'day0': [], 'day2': [{'method': 'del_ue'}], 'dayN': []}],
            'monitor': [{'day0': [], 'day2': [{'method': 'enable_prometheus'}], 'dayN': []}],
            'log': [{'day0': [], 'day2': [{'method': 'enable_elk'}], 'dayN': []}],
        }

        # DO NOT remove -> model initialization.
        self.uer_model = UeransimModel.model_validate(self.base_model.conf)
        # Avoid putting self.db
        # FIXME: how to connect radionets among different vims??

    def vim_terraform(self, msg):
        """
        Creates required resources on the VIM.
        Creates a network on the VIM for Ueransim (radio_{BLUE_ID}, 10.168.0.0/16).

        Args:
            msg: msg['areas'] contains the area on witch the net is created
        """
        net: NetworkModel = NetworkModel.build_network_model(self._get_radio_net_name(), NetworkTypeEnum.vxlan, IPv4Network(self.RADIO_NET_CIDR))
        net.allocation_pool = [IPv4Pool(start=IPv4Address(self.RADIO_NET_CIDR_START), end=IPv4Address(self.RADIO_NET_CIDR_END))]

        topo = self.get_topology()
        area_id_list = [item.id for item in self.uer_model.areas]
        topo.add_network_by_area(net, area_id_list, terraform=True)

    def bootstrap_day0(self, msg: dict) -> list:
        self.check_pdu_area(msg)
        self.vim_terraform(msg)
        return self.nsd()

    def set_ue_vnfd(self, interfaces: List[VimLink], ue_id: int):
        """
        Build VNFD for UE
        Args:
            interfaces: the list of attached interfaces to VNF
            ue_id: The ID of the User Equipment

        Returns: the vnfd summary
        """
        if ue_id is None:
            raise ValueError('UE id should be provided to build the VNFd')

        # Create the VDU for a UE
        ue_vdu = VirtualDeploymentUnit.build_vdu_vim_link('VM', self.VM_IMAGE, interfaces, self.UE_FLAVOR)

        # Build the vnfd package
        ue_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            f"{self.get_id()}_ue_{ue_id}",
            vnf_username=self.DEFAULT_USER,
            vnf_passwd=self.DEFAULT_PASSWORD,
            vdu_list=[ue_vdu]
        )

        # Build the VNF package and upload the package on OSM
        built_vnfd_package = Sol006VnfdBuilderBeta(ue_vnfd, hemlflexcharm=True, cloud_init=True)

        vnfd_summary = built_vnfd_package.get_vnf_blue_descr_only_vdu()

        self.base_model.vnfd.ues.append(vnfd_summary)

        self.to_db()

        return vnfd_summary

    def set_nb_vnfd(self, interfaces: List[VimLink], area: UeransimArea):
        """
        Build VNFD for NB
        Args:
            interfaces: the list of attached interfaces to VNF
            ue_id: The ID of the User Equipment

        Returns: the vnfd summary
        """
        if area is None:
            raise ValueError('UE id should be provided to build the VNFd')

        # Create the VDU for a UE
        ue_vdu = VirtualDeploymentUnit.build_vdu_vim_link('VM', self.VM_IMAGE, interfaces, self.GNB_FLAVOR)

        # Build the vnfd package
        ue_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            f"{self.get_id()}_ue_{area.id}", # self.get_id() + '_nb_' + str(area.id)
            vnf_username=self.DEFAULT_USER,
            vnf_passwd=self.DEFAULT_PASSWORD,
            vdu_list=[ue_vdu]
        )

        # Build the VNF package and upload the package on OSM
        built_vnfd_package = Sol006VnfdBuilderBeta(ue_vnfd, hemlflexcharm=True, cloud_init=True)

        vnfd_summary = built_vnfd_package.get_vnf_blue_descr_only_vdu()

        self.base_model.vnfd.ues.append(vnfd_summary)

        self.to_db()

        return vnfd_summary

    def nb_nsd(self, area: UeransimArea) -> str:
        """
        Build NSD for NB
        Args:
            area: The area on witch the service is deployed

        Returns:

        """
        logger.info("building NB NSD for area " + str(area.id))

        net_list: List[VimNetMap] = []
        vim_link_list: List[VimLink] = []

        # Adding the mngt vim link
        mgt_vim_net_map = VimNetMap.build_vnm("mgt","ens3",self.uer_model.config.network_endpoints.mgt,True)
        net_list.append(mgt_vim_net_map)
        vim_link_list.append(VimLink.build_vim_link(mgt_vim_net_map))

        # Adding the data vim link if not corresponding to the mgt one
        if not (self.uer_model.config.network_endpoints.mgt == self.uer_model.config.network_endpoints.wan or not self.uer_model.config.network_endpoints.wan):
            data_vim_net_map = VimNetMap.build_vnm("datanet", "ens4", self.uer_model.config.network_endpoints.mgt, False)
            net_list.append(data_vim_net_map)
            vim_link_list.append(VimLink.build_vim_link(data_vim_net_map))

        # Adding the radio vim link
        radio_vim_net_map = VimNetMap.build_vnm("radionet", "ens5", f"radio_{self.get_id()}", False)
        net_list.append(radio_vim_net_map)
        vim_link_list.append(VimLink.build_vim_link(radio_vim_net_map))

        # Creating VNFD for NB (uploads it into OSM)
        nb_created_vnfd = [self.set_nb_vnfd(vim_link_list, area)]

        ns_id = f'{self.get_id()}_nb_tac_{area.id}'
        nsd_builder = Sol006NSDBuilderBeta(
            nb_created_vnfd,
            self.get_topology().get_vim_name_from_area_id(area.id),
            nsd_id=ns_id,
            nsd_type=self.GNB_NS_TYPE,
            vl_maps=net_list
        )

        nsd = nsd_builder.get_nsd()

        nsd.area_id = area.id

        # Append to the NSD list the created NSD.
        self.base_model.nsd_.append(nsd)
        self.to_db()  # Save the model

        return ns_id

    def ue_nsd(self, ue: UeransimUe, area: UeransimArea) -> str:
        """
        Build NSD for NB
        Args:
            area: The area on witch the service is deployed

        Returns:

        """
        logger.info("building NSD for UE " + str(ue.id))

        net_list = []
        vim_link_list: List[VimLink] = []

        # Adding the mngt vim link
        mgt_vim_net_map = VimNetMap.build_vnm("mgt", "ens3", self.uer_model.config.network_endpoints.mgt, True)
        net_list.append(mgt_vim_net_map)
        vim_link_list.append(VimLink.build_vim_link(mgt_vim_net_map))

        # Adding the radio vim link
        radio_vim_net_map = VimNetMap.build_vnm("radionet", "ens5", f"radio_{self.get_id()}", False)
        net_list.append(radio_vim_net_map)
        vim_link_list.append(VimLink.build_vim_link(radio_vim_net_map))

        # Creating VNFD for NB (uploads it into OSM)
        nb_created_vnfd = [self.set_ue_vnfd(vim_link_list, ue.id)]

        ns_id = f'{self.get_id()}_ue_{ue.id}'
        nsd_builder = Sol006NSDBuilderBeta(
            nb_created_vnfd,
            self.get_topology().get_vim_name_from_area_id(area.id),
            nsd_id=ns_id,
            nsd_type=self.UE_NS_TYPE,
            vl_maps=net_list
        )

        nsd = nsd_builder.get_nsd()

        nsd.area_id = area.id
        nsd.ue_id = ue.id

        # Append to the NSD list the created NSD.
        self.base_model.nsd_.append(nsd)
        # Append interface list of gNB interfaces to the area
        area.gnb_interface_list = net_list
        self.to_db()  # Save the model

        return ns_id

    def nsd(self) -> list:
        """
        Creates required NSDs that depend on the request

        Returns: nsd names of created NSD
        """
        logger.info("Creating UeRanSim Network Service Descriptors")
        nsd_names = []

        # For each area creates a gNB
        for area in self.uer_model.areas:
            logger.info("Creating UeRanSim NB vnfd on area {}".format(area.id))
            nsd_names.append(self.nb_nsd(area))

            # In each area creates the required number of UEs (present in the request)
            for ue in area.ues:
                logger.info("Creating UeRanSim UE vnfd on area {} with ID {}".format(area.id, ue.id))
                nsd_names.append(self.ue_nsd(ue, area))

        logger.debug("NSDs created")
        return nsd_names

    def check_pdu_area(self, msg: dict):
        """
        Checks that PDU is not already exising
        """
        for area in self.uer_model.areas:
            # Check if there is not a PDU in every involved area. TODO: is it correct?
            if self.topology_get_pdu_by_area(area.id):
                self.base_model.status = 'error'
                self.base_model.detailed_status = 'PDU at area {} already existing'.format(area.id)
                raise ValueError(self.base_model.detailed_status)

    def init_day2_conf(self, msg: dict) -> list:
        logger.info("Triggering day2 operations for ueransim blueprint with id {}".format(self.get_id()))

        res = []
        gnb_radio_ips = []
        ue_nsd_list = [] # A list of UE's nsd

        # Configuration needs to be done in each existing NS
        for nsd_item in self.base_model.nsd_:
            match nsd_item.type:
                # before we have to get info from all the NodeBs (IP address on the radio interface), then we can pass to UEs
                case self.GNB_NS_TYPE:
                    for area in self.uer_model.areas:
                        # Looking for area of the NSD
                        if nsd_item.area_id == area.id:
                            pdu_interfaces: List[PduInterface] = []
                            for nb_interface in area.gnb_interface_list:
                                # Radio emulation net should not be added to the pdu, which, like real NBs, should
                                # have only mgt and data links
                                if not nb_interface.vld == "radionet":
                                    pdu_interf = PduInterface.build_pdu(nb_interface.vld, nb_interface.name, nb_interface.mgt, nb_interface.ip_address, nb_interface.vim_net)
                                    pdu_interfaces.append(pdu_interf)
                                else:
                                    # Adding the radionet IP as the radio IP of the gNB
                                    gnb_radio_ips.append(nb_interface.ip_address)

                            # NOTE the actual config of the NB will be pushed later, we are preparing only the pnf here
                            pdu_obj = {
                                'name': f'nb_{area.id}',
                                'area': area.id,
                                'type': self.GNB_NS_TYPE,
                                'user': self.DEFAULT_USER,
                                'passwd': self.DEFAULT_PASSWORD,
                                'implementation': "ueransim_nb",
                                'nfvo_onboarded': False,
                                'config': {'cell_id': '{}'.format(hex(1000 + area.id)), 'radio_addr': gnb_radio_ips[-1]},
                                'interface': pdu_interfaces
                            }
                            # Add the PDU to the topology
                            self.topology_add_pdu(PduModel.model_validate(pdu_obj))

                case self.UE_NS_TYPE:
                    # Saving list of UEs to be iterated later (no double for loop)
                    ue_nsd_list.append(nsd_item)
                case _:
                    raise ValueError("Case not recognized")

        # Now lets configure UEs
        for ue_nsd in ue_nsd_list:
            for area in self.uer_model.areas:
                for ue in area.ues:
                    ue.vim_gnbs_ips = gnb_radio_ips
                    if ue.id == ue_nsd.ue_id:
                        config = ConfiguratorUeUeRanSimBeta(
                            ue_nsd.descr.nsd.nsd[0].id,
                            1,
                            self.get_id(),
                            ue
                        ).dump()
                        res += config

        self.to_db()
        return res

    def add_ue(self, msg: UeranSimBlueprintRequestAddDelUe) -> list:
        """
        Add a UERanSim simulated UE to the blueprint. The device is emulated in addition to existing ones.
        Args:
            msg: The request message coming from the APIs

        Returns:

        """
        logger.debug("Adding UE(s) to UeRanSim blueprint " + str(self.get_id()))
        nsd_names = []

        for area in msg.areas:
            # Check that the VIM exist for that area
            try:
                vim = self.get_topology().get_vim_name_from_area_id(area.id)
            except ValueError as e:
                # VIM for area has not been found
                self.raise_http_error(str(e), status_code=status.HTTP_404_BAD_REQUEST)

            if area not in self.uer_model.areas:  # Works thanks to equals override in the model
                self.uer_model.areas.append(area)

            for user_eq in area.ues:
                # Check if the user equipment is not already existing
                # Get the correspondent area if existing

                nsd_names.append(self.ue_nsd(user_eq, area))

        return nsd_names

    def get_ip(self):
        """
        Retrieve every IP address of created NSs. We don't know IPs until VMs are created from OpenStack
        """
        logger.info('Getting IP addresses from vnf instances')

        for nsd in self.base_model.nsd_:
            logger.debug("Getting IPs of nsi {}".format(nsd.nsd_id))

            # Looking for the area of the NSD
            for area in self.uer_model.areas:
                # When the correct area is found -> If the nsd is the gNB type then getting its IP address
                if nsd.type == self.GNB_NS_TYPE and area.id == nsd.area_id:
                    vlds = get_ns_vld_model(nsd.nsi_id, ["mgt", "datanet", "radionet"])
                    logger.debug(f"NSI {nsd.nsd_id} is a gNB. Getting IP addresses from vlds.")
                    for interface in area.gnb_interface_list:
                        interface.ip_address = vlds[interface.vld][0].get_ip_list_str()[0]
                        logger.debug(f"NSI {nsd.nsd_id} on int {interface.name} IP is {interface.ip_address}")

                # When the correct area is found and UE type
                if nsd.type == self.UE_NS_TYPE and area.id == nsd.area_id:
                    # Looking for the correct UE in the area
                    for user_eq in area.ues:
                        vlds = get_ns_vld_model(nsd.nsi_id, ["mgt", "radionet"])
                        logger.debug(f"NSI {nsd.nsd_id} is a UE. Getting IP addresses from vlds.")
                        for interface in area.gnb_interface_list:
                            interface.ip_address = vlds[interface.vld][0].get_ip_list_str()[0]
                            logger.debug(f"NSI {nsd.nsd_id} on int {interface.name} IP is {interface.ip_address}")

        logger.info("VNFs' IP addresses acquired")
        self.to_db()

    def _destroy(self):
        logger.debug("Destroying UeRanSim specific resources")
        logger.debug("Deleting radio net")

        topology = self.get_topology()

        # Delete the network on each VIM
        try:
            topology.del_network_by_name(self._get_radio_net_name(), terraform=True)
        except ValueError as e:
            logger.warning(f"Blueprint destroy error: {e}")

    def _get_radio_net_name(self):
        """
        Return the radio name to be used by the blueprint
        """
        return f"radio_{self.get_id()}"

    def get_data(self, get_request: BlueGetDataModel):
        pass
