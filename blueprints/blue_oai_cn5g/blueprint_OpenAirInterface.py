import copy
import json
from typing import List, Union, Dict, Optional

import httpx
import yaml

from blueprints.blue_5g_base.blueprint_5g_base_beta import Blue5GBaseBeta, SstConvertion, CoreArea5G, Area5GTypeEnum, \
    RanArea5G, EdgeArea5G
from blueprints.blue_5g_base.models.blue_5g_model import SubSliceProfiles, SubDataNets, SubArea, SubSlices
from blueprints.blue_oai_cn5g.config import oai_default_config
from blueprints.blue_oai_cn5g.configurator.upf_configurator import Configurator_OAI_UPF, ConfiguratorOAIUPFVars
from blueprints.blue_oai_cn5g.configurator.upf_reloader import Reloader_OAI_UPF
from blueprints.blue_oai_cn5g.models import OAIBlueCreateModel
from blueprints.blue_oai_cn5g.models.blue_OAI_model import OAIModel, OAIModelServices, \
    SessionManagementSubscription, Ue, SessionManagementSubscriptionData, OAIAddSubscriberModel, \
    OAIDelSubscriberModel, BlueprintOAIBaseModel, Currentconfig, Snssai, SNssaiUpfInfoListItem, \
    Dnn, HostAliase, UpfAvailable, DnnItem, PlmnSupportListItem, ServedGuamiListItem, SNssaiSmfInfoListItem, \
    LocalSubscriptionInfo, QosProfile, OaiSmf, OAIAddSliceModel, OAIDelSliceModel, DnnConfiguration, SessionAmbr, \
    FiveQosProfile, OAIAddTacModel, OAIDelTacModel
from models.blueprint.blueprint_base_model import BlueKDUConf, BlueVNFD, BlueNSD
from models.blueprint.rest_blue import BlueGetDataModel
from models.vim import VimModel
from models.vim.vim_models import VimNetMap, KubeDeploymentUnit, VirtualNetworkFunctionDescriptor, \
    VirtualDeploymentUnit
from nfvo.nsd_manager_beta import Sol006NSDBuilderBeta, get_kdu_services, get_ns_vld_ip
from nfvo.osm_nbi_util import get_osm_nbi_utils
from nfvo.vnf_manager_beta import Sol006VnfdBuilderBeta
from utils.log import create_logger
from utils.persistency import DB

db = DB()
nbiUtil = get_osm_nbi_utils()
logger = create_logger('OpenAirInterface')


class OpenAirInterface(Blue5GBaseBeta):
    CHART_NAME = "nfvcl/oai5gbasic"
    KDU_NAME = "oai5gbasic"
    VNF_ID_SUFFIX = "oai5gbasic"
    NS_ID_INFIX = "OAI5GBASIC"
    UPF_IMG_NAME = "UPF_OpenAirInterface5G_V2"

    @classmethod
    def rest_create(cls, msg: OAIBlueCreateModel):
        return cls.api_day0_function(msg)

    @classmethod
    def rest_add_subscriber(cls, add_subscriber_model: OAIAddSubscriberModel, blue_id: str):
        return cls.api_day2_function(add_subscriber_model, blue_id)

    @classmethod
    def rest_del_subscriber(cls, del_subscriber_model: OAIDelSubscriberModel, blue_id: str):
        return cls.api_day2_function(del_subscriber_model, blue_id)

    @classmethod
    def rest_add_slice(cls, add_slice_model: OAIAddSliceModel, blue_id: str):
        return cls.api_day2_function(add_slice_model, blue_id)

    @classmethod
    def rest_del_slice(cls, del_slice_model: OAIDelSliceModel, blue_id: str):
        return cls.api_day2_function(del_slice_model, blue_id)

    @classmethod
    def rest_add_tac(cls, add_tac_model: OAIAddTacModel, blue_id: str):
        return cls.api_day2_function(add_tac_model, blue_id)

    @classmethod
    def rest_del_tac(cls, del_tac_model: OAIDelTacModel, blue_id: str):
        return cls.api_day2_function(del_tac_model, blue_id)

    @classmethod
    def day2_methods(cls):
        cls.api_router.add_api_route(
            path="/{blue_id}/add_tac",
            endpoint=cls.rest_add_tac,
            methods=["PUT"],
            description="Add tac",
            summary="Add tac"
        )
        cls.api_router.add_api_route(
            path="/{blue_id}/del_tac",
            endpoint=cls.rest_del_tac,
            methods=["PUT"],
            description="Del tac",
            summary="Del tac"
        )
        cls.api_router.add_api_route(
            path="/{blue_id}/add_slice",
            endpoint=cls.rest_add_slice,
            methods=["PUT"],
            description="Add slice",
            summary="Add slice"
        )
        cls.api_router.add_api_route(
            path="/{blue_id}/del_slice",
            endpoint=cls.rest_del_slice,
            methods=["PUT"],
            description="Del slice",
            summary="Del slice"
        )
        cls.api_router.add_api_route(
            path="/{blue_id}/add_subscriber",
            endpoint=cls.rest_add_subscriber,
            methods=["PUT"],
            description="Add subscriber",
            summary="Add subscriber"
        )
        cls.api_router.add_api_route(
            path="/{blue_id}/del_subscriber",
            endpoint=cls.rest_del_subscriber,
            methods=["PUT"],
            description="Del subscriber",
            summary="Del subscriber"
        )

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None) -> None:
        Blue5GBaseBeta.__init__(self, conf, id_, data=data, db=db, nbiutil=nbiUtil)
        self.slices_list: List[SessionManagementSubscription] = list()
        self.db_connection = None
        self.upf_ip = None
        logger.info("Creating \"OpenAirInterface\" Blueprint")

        if data:
            logger.warning("Blueprint loaded from db, skipping init")
            self.base_model: BlueprintOAIBaseModel = BlueprintOAIBaseModel.model_validate(data)
        else:
            self.base_model = BlueprintOAIBaseModel.model_validate(self.base_model.model_dump())
            self.base_model.blue_model_5g = OAIModel.model_validate(self.base_model.conf)

            self.base_model.blue_model_5g.oai_config_values = copy.deepcopy(oai_default_config.default_config)

            self.init_base()

        self.base_model.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [{'method': 'init_day2_conf'}],
                'dayN': []
            }],
            'add_tac': [{
                'day0': [{'method': 'add_tac', 'callback': 'add_tac_callback'}],
                'day2': [{'method': 'add_tac_day2'}],
                'dayN': []
            }],
            'del_tac': [{
                'day0': [],
                'day2': [{'method': 'del_tac_day2'}],
                'dayN': [{'method': 'del_tac', 'callback': 'del_tac_callback'}]
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
                'day2': [{'method': 'add_slice'}],
                'dayN': []
            }],
            'del_slice': [{
                'day0': [],
                'day2': [{'method': 'del_slice'}],
                'dayN': []
            }]
        }

    def add_slice_to_conf(self, add_slice_model: OAIAddSliceModel) -> bool:
        """
        Add new slice to "sliceProfiles" initial configuration.
        If area id is provided then new slice is also added to "areas" initial configuration.
        :param add_slice_model: New slice data.
        :return: False if slice already exists.
                 If area provided and slice added to "areas" True otherwise False.
                 True if not provided area and slice doesn't exist.
        """
        new_slice: SubSliceProfiles = SubSliceProfiles.model_validate(add_slice_model.model_dump(by_alias=True))
        if any(sub_slice.sliceId == new_slice.sliceId for sub_slice in self.base_model.blue_model_5g.config.sliceProfiles):
            return False
        self.base_model.blue_model_5g.config.sliceProfiles.append(new_slice)
        if add_slice_model.area_id is not None:
            area = self.get_area(add_slice_model.area_id)
            if area:
                area.slices.append(SubSlices(
                    sliceType=new_slice.sliceType,
                    sliceId=new_slice.sliceId
                ))
                return True
            else:
                return False
        return True

    def del_slice_from_conf(self, sub_slice: SubSliceProfiles, sub_area: SubArea = None) -> bool:
        """
        Delete a slice from "sliceProfiles" initial configuration.
        :param sub_slice: Slice to remove.
        :param sub_area: Area of the slice to remove (optional, default is None).
        :return: True if successfully removed slice from specified area, False otherwise (if area provided).
                 True if successfully removed slice, False otherwise (if area not provided).
        """
        if sub_slice and sub_area:
            for slice in sub_area.slices:
                if slice.sliceId == sub_slice.sliceId:
                    self.base_model.blue_model_5g.config.sliceProfiles.remove(sub_slice)
                    sub_area.slices.remove(slice)
                    return True
            return False
        elif sub_slice and not sub_area:
            self.base_model.blue_model_5g.config.sliceProfiles.remove(sub_slice)
            return True
        return False

    def get_slice(self, slice_id: str) -> Optional[SubSliceProfiles]:
        """
        Get slice from "sliceProfiles".
        :param slice_id: id of slice to retrieve.
        :return: Slice if exists, None otherwise.
        """
        for slice in self.base_model.blue_model_5g.config.sliceProfiles:
            if slice.sliceId == slice_id:
                return slice
        return None

    def get_area(self, area_id: int) -> Optional[SubArea]:
        """
        Get area from "areas".
        :param area_id: id of area to retrieve.
        :return: Area if exists, None otherwise.
        """
        for area in self.base_model.blue_model_5g.areas:
            if area_id == area.id:
                return area
        return None

    def get_area_from_sliceid(self, sliceid: str) -> Optional[SubArea]:
        """
        Get area from "areas".
        :param sliceid: id of slice that have to be in area.
        :return: Area with that slice, None otherwise.
        """

        for area in self.base_model.blue_model_5g.areas:
            for slice in area.slices:
                if slice.sliceId == sliceid:
                    return area
        return None

    def get_dnn(self, dnn_name: str) -> Optional[SubDataNets]:
        """
        Get dnn from "network_endpoints" -> "data_nets".
        :param dnn_name: name of dnn to retrieve.
        :return: Dnn if exists, None otherwise.
        """
        for dnn in self.base_model.blue_model_5g.config.network_endpoints.data_nets:
            if dnn_name == dnn.dnn:
                return dnn
        return None

    def bootstrap_day0(self, model_msg) -> list:
        return self.nsd()

    def core_vnfd(self, area: CoreArea5G, vls: List[VimNetMap]) -> List[BlueVNFD]:
        core_kdu = KubeDeploymentUnit.build_kdu(
            name=self.KDU_NAME,
            helm_chart=self.CHART_NAME,
            interface=vls
        )
        core_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            vnf_id=f'{self.get_id()}_{self.VNF_ID_SUFFIX}',
            kdu_list=[core_kdu]
        )
        build_core_vnfd_package = Sol006VnfdBuilderBeta(core_vnfd)
        blue_vnfd = build_core_vnfd_package.get_vnf_blue_descr_only_kdu()
        self.base_model.vnfd.core.append(blue_vnfd)
        self.to_db()
        return [blue_vnfd]

    def core_nsd(self, area: CoreArea5G) -> List[str]:
        logger.info(f"Creating Core NSD in area {area.id}")

        vim_net_mapping = VimNetMap.build_vnm(
            "mgt",
            self.MGT_NETWORK_IF_NAME,
            self.base_model.networks_5g.mgt,
            True,
            "mgt_net"
        )

        vnfd_k8s = self.core_vnfd(area, vls=[vim_net_mapping])

        kdu_config = BlueKDUConf(
            kdu_name=self.KDU_NAME,
            k8s_namespace=str(self.get_id()).lower(),
            additionalParams=self.base_model.blue_model_5g.oai_config_values.model_dump(exclude_none=True, by_alias=True)
        )

        nsd_id = f"{self.get_id()}_OAI5G_{self.base_model.blue_model_5g.config.plmn}"

        n_obj = Sol006NSDBuilderBeta(
            vnfds=vnfd_k8s,
            vim_name=self.base_model.core_vim.name,
            nsd_id=nsd_id,
            nsd_type=Area5GTypeEnum.CORE.value,
            vl_maps=[vim_net_mapping],
            knf_configs=[kdu_config]
        )

        nsd_item = n_obj.get_nsd()
        nsd_item.area_id = area.id
        self.base_model.nsd_.append(nsd_item)
        area.nsd = nsd_item
        self.to_db()
        return [nsd_id]

    def edge_vnfd(self, area: EdgeArea5G, vls: List[VimNetMap]) -> List[BlueVNFD]:
        edge_vdu = VirtualDeploymentUnit.build_vdu(
            vdu_id=f'{self.get_id()}_upf_oai5g_{area.id}',
            vdu_image=self.UPF_IMG_NAME,
            vdu_data_int_list=list(map(lambda x: x.vim_net, vls[1:])),  # Skip first net, mgt
        )
        edge_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            vnf_username="root",
            vnf_passwd="root",
            cloud_init=True,
            vnf_id=f'{self.get_id()}_UPF_OAI5G_{area.id}',
            vdu_list=[edge_vdu]
        )
        build_edge_vnfd_package = Sol006VnfdBuilderBeta(edge_vnfd, cloud_init=True, hemlflexcharm=True)
        blue_vnfd = build_edge_vnfd_package.get_vnf_blue_descr_only_vdu()
        self.base_model.vnfd.area.append(blue_vnfd)
        self.to_db()
        return [blue_vnfd]

    def edge_nsd(self, area: EdgeArea5G) -> List[str]:
        logger.info(f"Creating Edge NSD(s) in area {area.id}")

        edge_vim: VimModel = self.get_topology().get_vim_from_area_id_model(area.id)

        vim_net_mapping1 = VimNetMap.build_vnm(
            "mgt",
            self.MGT_NETWORK_IF_NAME,
            self.base_model.networks_5g.mgt,
            True,
            "data_net"
        )

        vim_net_mapping2 = VimNetMap.build_vnm(
            f"data_{self.base_model.networks_5g.wan}",
            self.WAN_NETWORK_IF_NAME,
            self.base_model.networks_5g.wan,
            False,
            "data_net"
        )

        edge_vnfd = self.edge_vnfd(area, vls=[vim_net_mapping1, vim_net_mapping2])

        nsd_id = f"{self.get_id()}_UPF_OAI5G_{area.id}_{self.base_model.blue_model_5g.config.plmn}"

        n_obj = Sol006NSDBuilderBeta(
            vnfds=edge_vnfd,
            vim_name=edge_vim.name,
            nsd_id=nsd_id,
            nsd_type=Area5GTypeEnum.EDGE.value,
            vl_maps=[vim_net_mapping1, vim_net_mapping2]
        )

        nsd_item = n_obj.get_nsd()
        nsd_item.area_id = area.id
        self.base_model.nsd_.append(nsd_item)
        area.nsd = nsd_item
        self.to_db()
        return [nsd_id]

    def get_ip_core(self, n: BlueNSD) -> None:
        """
        Get ip of core service.
        :param n: NSD of the core.
        :return: None.
        """
        try:
            kdu_services = get_kdu_services(n.nsi_id, self.KDU_NAME)
            kdu_services_dict = {}
            for kdu_service in kdu_services:
                kdu_services_dict[kdu_service.name] = kdu_service
            self.base_model.blue_model_5g.core_services = OAIModelServices.model_validate(kdu_services_dict)
            self.base_model.core_area.amf_ip = self.base_model.blue_model_5g.core_services.amf.external_ip[0]
        except Exception as e:
            logger.exception("Exception in get_ip_core")

    def get_ip_edge(self, n: BlueNSD) -> None:
        """
        Get ip of edge service.
        :param n: NSD of the edge.
        :return: None.
        """
        vlds = get_ns_vld_ip(n.nsi_id, ["mgt", f'data_{self.base_model.networks_5g.wan}'])
        self.base_model.edge_areas[n.area_id].upf_mgt_ip = vlds["mgt"][0]['ip']
        self.base_model.edge_areas[n.area_id].upf_data_ip = vlds[f'data_{self.base_model.networks_5g.wan}'][0]['ip']

        core_data_network = self.topology_get_network(self.base_model.networks_5g.wan)
        self.base_model.edge_areas[n.area_id].upf_data_network_cidr = str(core_data_network.cidr)

        logger.debug(f'MGT IP for edge: {self.base_model.edge_areas[n.area_id].upf_mgt_ip}')
        logger.debug(f'DATA IP for edge: {self.base_model.edge_areas[n.area_id].upf_data_ip}')
        logger.debug(f'DATA NETWORK CIDR for edge: {self.base_model.edge_areas[n.area_id].upf_data_network_cidr}')
        logger.debug(f'END Getting IPs for edge area {n.area_id}')

    def get_additional_ran_conf(self, area: RanArea5G) -> dict:
        return {}

    def _destroy(self):
        pass

    def get_ip(self) -> None:
        super().get_ip()

    def pre_initialization_checks(self) -> bool:
        pass

    def get_data(self, get_request: BlueGetDataModel):
        pass

    def core_upXade(self, msg: dict) -> list:
        pass

    ###### Start utility function to edit config values ######
    def add_snssai(self, config: Currentconfig, slice_id: str, slice_type: str) -> Snssai:
        """
        Add new "snssai" to OAI values configuration.
        :param config": config to add snssai to.
        :param slice_id: slice id of snssai to add.
        :param slice_type: slice type of snssai to add.
        :return: new snassai otherwise raise an error.
        """
        new_snssais = Snssai(
            sst=SstConvertion.to_int(slice_type),
            sd=slice_id
        )
        if new_snssais not in config.snssais:
            config.snssais.append(new_snssais)
            return new_snssais
        raise ValueError(f"Add failed, slice {slice_id} already exist")

    def del_snssai(self, config: Currentconfig, slice_id: str) -> Snssai:
        """
        Delete "snssai" from OAI values configuration.
        :param config: config to remove snssai from.
        :param slice_id: slice id of the snssai to delete.
        :return: deleted snssai otherwise raise an error.
        """
        for snssai in config.snssais:
            if snssai.sd == slice_id:
                config.snssais.remove(snssai)
                return snssai
        raise ValueError(f"Delete failed, slice {slice_id} doesnt exist")

    def add_dnn_dnns(self, config: Currentconfig, dnn: str) -> Optional[Dnn]:
        """
        Add "dnn" to OAI values configuration.
        :param config: config to add dnn.
        :param dnn: dnn to add.
        :return: new dnn otherwise None.
        """
        sub_dnn = self.get_dnn(dnn)
        new_dnn = Dnn(
            dnn=sub_dnn.dnn,
            ipv4_subnet=sub_dnn.pools[0].cidr
        )
        if new_dnn not in config.dnns:
            config.dnns.append(new_dnn)
            return new_dnn
        return None

    def del_dnn_dnns(self, config: Currentconfig, dnn_to_remove: str) -> bool:
        """
        Delete "dnn" to OAI values configuration.
        :param config: config to remove dnn from.
        :param dnn_to_remove: dnn to remove.
        :return: True if removed, False otherwise.
        """
        for dnn in config.dnns:
            if dnn.dnn == dnn_to_remove:
                config.dnns.remove(dnn)
                return True
        return False

    def create_snssai_upf_info_list_item(self, config: Currentconfig, nssai: Snssai) -> Optional[SNssaiUpfInfoListItem]:
        """
        Add new item to OAI values configuration "snssai_upf_info_list".
        :param config: config to add the item to.
        :param nssai: snssai of the item.
        :return: new item, if it already exists None.
        """
        new_s_nssai_item = SNssaiUpfInfoListItem(
            sNssai=nssai,
            dnnUpfInfoList=[]
        )
        if new_s_nssai_item not in config.upf.upf_info.sNssaiUpfInfoList:
            config.upf.upf_info.sNssaiUpfInfoList.append(new_s_nssai_item)
            return new_s_nssai_item
        return None

    def destroy_snssai_upf_info_list_item(self, config: Currentconfig, slice_id: str) -> bool:
        """
        Delete item from values configuration "snssai_upf_info_list".
        :param config: config to delete the item from.
        :param slice_id: slice id of nssai.
        :return: True if the item was successfully deleted, otherwise False.
        """
        for item in config.upf.upf_info.sNssaiUpfInfoList:
            if item.sNssai.sd == slice_id:
                config.upf.upf_info.sNssaiUpfInfoList.remove(item)
                return True
        return False

    def add_dnn_snssai_upf_info_list_item(self, config: Currentconfig, snssai: Snssai, dnn: DnnItem) -> Optional[bool]:
        """
        Add item to OAI values configuration "dnn_snssai_upf_info_list", if "snssai_upf_info_list" doesn't exist
        it will be created and then item added.
        :param config: config to add the item to.
        :param snssai: snssai of the item.
        :param dnn: dnn of the item.
        :return: True if the item was successfully added, otherwise None.
        """
        for item in config.upf.upf_info.sNssaiUpfInfoList:
            if item.sNssai.sd == snssai.sd:
                if dnn not in item.dnnUpfInfoList:
                    item.dnnUpfInfoList.append(dnn)
                return True
        self.create_snssai_upf_info_list_item(config, snssai)
        self.add_dnn_snssai_upf_info_list_item(config, snssai, dnn)

    def add_served_guami_list_item(self, config: Currentconfig, mcc: str, mnc: str) -> Optional[ServedGuamiListItem]:
        """
        Add item to OAI values configuration "served_guami_list".
        :param config: config to add the item to.
        :param mcc: mcc of the item.
        :param mnc: mnc of the item.
        :return: added item, otherwise None.
        """
        served_guami_list_item = ServedGuamiListItem(
            mcc=mcc,
            mnc=mnc,
            amf_region_id=mnc,
            amf_set_id=mcc,
            amf_pointer=mnc
        )
        if served_guami_list_item not in config.amf.served_guami_list:
            config.amf.served_guami_list.append(served_guami_list_item)
            return served_guami_list_item
        return None

    def del_served_guami_list_item(self, config: Currentconfig, mcc: str, mnc: str) -> bool:
        """
        Delete item from OAI values configuration "served_guami_list".
        :param config: config to delete the item from.
        :param mcc: mcc of the item.
        :param mnc: mnc of the item.
        :return: True if item was successfully deleted, otherwise False.
        """
        for item in config.amf.served_guami_list:
            if item.mcc == mcc and item.mnc == mnc:
                config.amf.served_guami_list.remove(item)
                return True
        return False

    def add_host_aliases(self, config: OaiSmf, area_id: int) -> HostAliase:
        """
        Add new "host alias" to OAI SMF configuration.
        :param config: config to add host alias to.
        :param area_id: area id of upf.
        :return: new host alias, raise an error otherwise.
        """
        new_hostalias = HostAliase(
            ip=self.base_model.edge_areas[area_id].upf_data_ip,
            hostnames=f"oai-upf{area_id}"
        )
        if new_hostalias not in config.hostAliases:
            config.hostAliases.append(new_hostalias)
            return new_hostalias
        raise ValueError(f"Add failed, oai-upf{area_id} already exist")

    def del_host_aliases(self, config: OaiSmf, area_id: int) -> bool:
        """
        Delete "host alias" from OAI SMF configuration.
        :param config: config to remove host alias from.
        :param area_id: area id of upf.
        :return: True if sucessfully delete host alias, otherwise raise an error.
        """
        for host in config.hostAliases:
            if host.hostnames == f"oai-upf{area_id}":
                config.hostAliases.remove(host)
                return True
        raise ValueError(f"Delete failed, oai-upf{area_id} doesnt exist")

    def add_available_upf(self, config: Currentconfig, area_id: int) -> Optional[UpfAvailable]:
        """
        Add "available upf" to OAI values configuration.
        :param config: config to add available upf to.
        :param area_id: area id of upf.
        :return: new available upf, otherwise None.
        """
        new_upf_supported = UpfAvailable(
            host=f"oai-upf{area_id}"
        )
        if new_upf_supported not in config.smf.upfs:
            config.smf.upfs.append(new_upf_supported)
            return new_upf_supported
        return None

    def del_available_upf(self, config: Currentconfig, area_id: int) -> bool:
        """
        Delete "available upf" from OAI values configuration.
        :param config: config to remove available upf from.
        :param area_id: area id of upf.
        :return: True if it was successfully deleted, otherwise False.
        """
        for upf in config.smf.upfs:
            if upf.host == f"oai-upf{area_id}":
                config.smf.upfs.remove(upf)
                return True
        return False

    def add_local_subscription_info(self, config: Currentconfig, snnsai: Snssai, dnn: str) -> Optional[LocalSubscriptionInfo]:
        """
        Add new "local_subscription_info" to OAI values configuration.
        :param config: config to add local_subscription_info to.
        :param snnsai: snnsai of local_subscription_info.
        :param dnn: dnn of local_subscription_info.
        :return: new local_subscription_info, otherwise None.
        """
        sub_dnn = self.get_dnn(dnn)
        local_subscription_info = LocalSubscriptionInfo(
            single_nssai=snnsai,
            dnn=sub_dnn.dnn,
            qos_profile=QosProfile(
                field_5qi=sub_dnn.default5qi,
                session_ambr_ul=sub_dnn.uplinkAmbr.replace(" ", ""),
                session_ambr_dl=sub_dnn.downlinkAmbr.replace(" ", "")
            )
        )
        if local_subscription_info not in config.smf.local_subscription_infos:
            config.smf.local_subscription_infos.append(local_subscription_info)
            return local_subscription_info
        return None

    def del_local_subscription_info(self, config: Currentconfig, slice_id: str, dnn: str) -> bool:
        """
        Delete "local_subscription_info" from OAI values configuration.
        :param config: config to delete local subscription info from.
        :param slice_id: slice id of snssai.
        :param dnn: dnn of local subscription info.
        :return: True if it was successfully deleted, False otherwise.
        """
        for info in config.smf.local_subscription_infos:
            if info.dnn == dnn and info.single_nssai.sd == slice_id:
                config.smf.local_subscription_infos.remove(info)
                return True
        return False

    def create_snssai_smf_info_list(self, config: Currentconfig, nssai: Snssai) -> Optional[SNssaiSmfInfoListItem]:
        """
        Add new item to OAI values configuration "snssai_smf_info_list".
        :param config: config to add the item to.
        :param nssai: snssai of the item.
        :return: new item, if it already exists None.
        """
        snssai_smf_info_list_item = SNssaiSmfInfoListItem(
            sNssai=nssai,
            dnnSmfInfoList=[]
        )
        if snssai_smf_info_list_item not in config.smf.smf_info.sNssaiSmfInfoList:
            config.smf.smf_info.sNssaiSmfInfoList.append(snssai_smf_info_list_item)
            return snssai_smf_info_list_item
        return None

    def destroy_snssai_smf_info_list_item(self, config: Currentconfig, slice_id: str) -> bool:
        """
        Delete item from values configuration "snssai_smf_info_list_item".
        :param config: config to delete the item from.
        :param slice_id: slice id of nssai.
        :return: True if the item was successfully deleted, otherwise False.
        """
        for item in config.smf.smf_info.sNssaiSmfInfoList:
            if item.sNssai.sd == slice_id:
                config.smf.smf_info.sNssaiSmfInfoList.remove(item)
                return True
        return False

    def add_dnn_snssai_smf_info_list_item(self, config: Currentconfig, nssai: Snssai, dnn: DnnItem) -> Optional[bool]:
        """
        Add item to OAI values configuration "dnn_snssai_smf_info_list", if "snssai_smf_info_list" doesn't exist
        it will be created and then item added.
        :param config: config to add the item to.
        :param snssai: snssai of the item.
        :param dnn: dnn of the item.
        :return: True if the item was successfully added, otherwise None.
        """
        for item in config.smf.smf_info.sNssaiSmfInfoList:
            if item.sNssai.sd == nssai.sd:
                if dnn not in item.dnnSmfInfoList:
                    item.dnnSmfInfoList.append(dnn)
                return True
        self.create_snssai_smf_info_list(config, nssai)
        self.add_dnn_snssai_smf_info_list_item(config, nssai, dnn)

    def create_plmn_list(self, config: Currentconfig, mcc: str, mnc: str, area_id: int) -> Optional[PlmnSupportListItem]:
        """
        Add new item to OAI values configuration "plmn_list".
        :param config: config to add the item to.
        :param mcc: mcc of the item.
        :param mnc: mnc of the item.
        :param area_id: area id of the item.
        :return: new plmn_item, otherwise None.
        """
        plmn_item = PlmnSupportListItem(
            mnc=mnc,
            mcc=mcc,
            tac=area_id,
            nssai=[]
        )
        if plmn_item not in config.amf.plmn_support_list:
            config.amf.plmn_support_list.append(plmn_item)
            return plmn_item
        return None

    def destroy_plmn_list(self, config: Currentconfig, mcc: str, mnc: str, area_id: int) -> bool:
        """
        Delete item from values configuration "plmn_list".
        :param config: config to delete the item from.
        :param mcc: mcc of the item.
        :param mnc: mnc of the item.
        :param area_id: area id of the item.
        :return: True if the item was successfully deleted, otherwise False.
        """
        for item in config.amf.plmn_support_list:
            if item.mcc == mcc and item.mnc == mnc and item.tac == area_id:
                config.amf.plmn_support_list.remove(item)
                return True
        return False

    def add_plmn_item(self, config: Currentconfig, mcc: str, mnc: str, area_id: int, nssai: Snssai) -> Optional[bool]:
        """
        Add item to OAI values configuration "plmn_list", if "plmn_list" doesn't exist
        it will be created and then item added.
        :param config: config to add the item to.
        :param mcc: mcc of the item.
        :param mnc: mnc of the item.
        :param area_id: area id of the.
        :param nssai: nssai of the item.
        :return: True if item was successfully added, otherwise None.
        """
        for item in config.amf.plmn_support_list:
            if item.mcc == mcc and item.mnc == mnc and item.tac == area_id:
                if nssai not in item.nssai:
                    item.nssai.append(nssai)
                return True
        self.create_plmn_list(config, mcc, mnc, area_id)
        self.add_plmn_item(config, mcc, mnc, area_id, nssai)

    def del_plmn_item(self, config: Currentconfig, mcc: str, mnc: str, area_id: int, nssai: Snssai) -> bool:
        """
        Delete item from OAI values configuration "plmn_list", if "plmn_list" it's empty
        it will be deleted.
        :param config: config to delete the item from.
        :param mcc: mcc of the item.
        :param mnc: mnc of the item.
        :param area_id: area id of the item.
        :param nssai: nssai of the item.
        :return: True if item was successfully deleted, otherwise False.
        """
        for item in config.amf.plmn_support_list:
            if item.mcc == mcc and item.mnc == mnc and item.tac == area_id and nssai in item.nssai:
                item.nssai.remove(nssai)
                if len(item.nssai) == 0:
                    self.destroy_plmn_list(config, mcc, mnc, area_id)
                return True
        return False

    def reload_upf(self, area: EdgeArea5G) -> list:
        """
        Reload the upf.
        :param area: area of upf to be reloaded.
        :return: day2 instruction to reload upf.
        """
        res = []
        logger.info(f"Restarting upf{area.id}")
        upf_restart = Reloader_OAI_UPF(area.nsd.descr.nsd.nsd[0].id, 1, self.get_id())
        res += upf_restart.dump()
        return res

    def reload_all_upf(self, except_id: int = None) -> list:
        """
        Reload all upfs.
        :param except_id: id of upf to exclude.
        :return: day2 instruction to reload all upf (except the one with id except_id, if except_id provided).
        """
        res = []
        for area_id in self.base_model.edge_areas.keys():
            if except_id is not None and area_id != except_id:
                res += self.reload_upf(self.base_model.edge_areas[area_id])
            else:
                res += self.reload_upf(self.base_model.edge_areas[area_id])
        return res

    ###### End utility function ######
    def edge_day2_conf(self, area: EdgeArea5G) -> list:
        """
        Configure upf on first boot.
        :param area: area of upf.
        :return: day2 instruction to configure upf at the first boot.
        """
        res = []
        upf_conf: Currentconfig = copy.deepcopy(oai_default_config.default_config.currentconfig)
        # Set value for UPF conf
        upf_conf.nfs.upf.host = f"oai-upf{area.id}"
        upf_conf.nfs.upf.sbi.interface_name = "ens4"
        upf_conf.nfs.upf.n3.interface_name = "ens4"
        upf_conf.nfs.upf.n4.interface_name = "ens4"
        upf_conf.nfs.upf.n6.interface_name = "ens3"
        upf_conf.nfs.upf.n9.interface_name = "ens4"

        # Clearing previous config
        upf_conf.snssais.clear()
        upf_conf.upf.upf_info.sNssaiUpfInfoList.clear()
        upf_conf.dnns.clear()

        sub_area = self.get_area(area.id)
        for slice in sub_area.slices:
            new_snssai: Snssai = self.add_snssai(upf_conf, slice.sliceId, slice.sliceType)
            sub_slice = self.get_slice(slice.sliceId)
            for dnn in sub_slice.dnnList:
                dnn_item = DnnItem(
                    dnn=dnn
                )
                # Add DNNS
                self.add_dnn_dnns(upf_conf, dnn)
                self.add_dnn_snssai_upf_info_list_item(upf_conf, new_snssai, dnn_item)

        upf_conf_yaml = yaml.dump(json.loads(upf_conf.model_dump_json(by_alias=True)))
        # Save UPF conf
        self.base_model.blue_model_5g.upf_config_dict[area.id] = upf_conf
        upf_configurator = Configurator_OAI_UPF(area.nsd.descr.nsd.nsd[0].id, 1, self.get_id(),
                                                ConfiguratorOAIUPFVars(
                                                    upf_id=area.id,
                                                    nrf_ipv4_address=self.base_model.blue_model_5g.core_services.nrf.external_ip[0],
                                                    upf_conf=upf_conf_yaml
                                                ))
        res += upf_configurator.dump()
        return res

    def core_day2_conf(self, area: CoreArea5G) -> list:
        """
        Configure core on first boot.
        :param area: area of core.
        :return: day2 instruction to configure core at the first boot.
        """
        logger.info("Initializing Core Day2 configurations")
        core_config = copy.deepcopy(oai_default_config.default_config)
        mcc = self.base_model.blue_model_5g.config.plmn[0:3]
        mnc = self.base_model.blue_model_5g.config.plmn[-2:]
        # Clear served_guami_list
        core_config.currentconfig.amf.served_guami_list.clear()
        self.add_served_guami_list_item(core_config.currentconfig, mcc, mnc)

        # Clear hostaliases
        core_config.oai_smf.hostAliases.clear()
        # Clear supported upf
        core_config.currentconfig.smf.upfs.clear()
        # Clear supported snssais
        core_config.currentconfig.snssais.clear()
        # Clear plmn support list
        core_config.currentconfig.amf.plmn_support_list.clear()
        # Clear sNssaiSmfInfoList
        core_config.currentconfig.smf.smf_info.sNssaiSmfInfoList.clear()
        # Clear local_subscription_infos
        core_config.currentconfig.smf.local_subscription_infos.clear()
        # Clear dnns
        core_config.currentconfig.dnns.clear()

        for sub_area in self.base_model.blue_model_5g.areas:
            # Add new host alias
            self.add_host_aliases(core_config.oai_smf, sub_area.id)
            # Add supported upf
            self.add_available_upf(core_config.currentconfig, sub_area.id)

            for slice in sub_area.slices:
                new_snssai = self.add_snssai(core_config.currentconfig, slice.sliceId, slice.sliceType)
                self.add_plmn_item(core_config.currentconfig, mcc, mnc, sub_area.id, new_snssai)
                sub_slice = self.get_slice(slice.sliceId)
                for dnn in sub_slice.dnnList:
                    dnn_item = DnnItem(
                        dnn=dnn
                    )
                    self.add_local_subscription_info(core_config.currentconfig, new_snssai, dnn)
                    self.add_dnn_dnns(core_config.currentconfig, dnn)
                    self.add_dnn_snssai_smf_info_list_item(core_config.currentconfig, new_snssai, dnn_item)

        for subscriber in self.base_model.blue_model_5g.config.subscribers:
            self.add_ues(subscriber)

        self.base_model.blue_model_5g.oai_config_values = core_config
        return self.kdu_upgrade(self.base_model.core_area.nsd, json.loads(core_config.model_dump_json(by_alias=True)), self.KDU_NAME)

    def core_init(self):
        pass

    def add_ues(self, subscriber_model: OAIAddSubscriberModel) -> list:
        """
        Calls OAI api to add new UE and his SMS (Session Management Subscription) to DB.
        :param subscriber_model: UE to add.
        """
        logger.info(f"Try to add user: {subscriber_model.imsi}")
        with httpx.Client(http1=False, http2=True) as client:
            # Add UE to DB
            api_url_ue = f"http://{self.base_model.blue_model_5g.core_services.udr.external_ip[0]}:80/nudr-dr/v2/subscription-data/{subscriber_model.imsi}/authentication-data/authentication-subscription"
            api_url_ue = f"http://{self.base_model.blue_model_5g.core_services.udr.external_ip[0]}:80/nudr-dr/v2/subscription-data/{subscriber_model.imsi}/authentication-data/authentication-subscription"
            payload_ue = Ue(
                authentication_method=subscriber_model.authenticationMethod,
                enc_permanent_key=subscriber_model.k,
                protection_parameter_id=subscriber_model.k,
                # authentication_management_field=subscriber_model.authenticationManagementField,
                enc_opc_key=subscriber_model.opc,
                enc_topc_key=subscriber_model.opc,
                supi=subscriber_model.imsi
            )
            response = client.put(api_url_ue, json=payload_ue.model_dump(by_alias=True))
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Response content: {response.text}")

            # Add Session Management Subscription to DB
            api_url_sms = f"http://{self.base_model.blue_model_5g.core_services.udr.external_ip[0]}:80/nudr-dr/v2/subscription-data/{subscriber_model.imsi}/{self.base_model.blue_model_5g.config.plmn}/provisioned-data/sm-data"
            new_slice = single_nssai = Snssai(
                sst=SstConvertion.to_int(subscriber_model.snssai[0].sliceType),
                sd=str(int(subscriber_model.snssai[0].sliceId, 16))
            )
            # Only 1 slice for subscriber and plmn is supported by OAI
            for subscriber_model.imsi in self.base_model.blue_model_5g.ue_dict.keys():
                self.base_model.blue_model_5g.ue_dict[subscriber_model.imsi][0] = single_nssai
            else:
                self.base_model.blue_model_5g.ue_dict[subscriber_model.imsi] = []
                self.base_model.blue_model_5g.ue_dict[subscriber_model.imsi].append(single_nssai)
            payload_sms = SessionManagementSubscriptionData(
                single_nssai=single_nssai
            )
            sub_slice = self.get_slice(subscriber_model.snssai[0].sliceId)
            for dnn in sub_slice.dnnList:
                sub_dnn = self.get_dnn(dnn)
                configuration = DnnConfiguration(
                    s_ambr=SessionAmbr(
                        uplink=sub_dnn.uplinkAmbr.replace(" ", ""),
                        downlink=sub_dnn.downlinkAmbr.replace(" ", "")
                    ),
                    five_qosProfile=FiveQosProfile(
                        five_qi=sub_dnn.default5qi
                    )
                )
                payload_sms.add_configuration(dnn, configuration)
                response = client.put(api_url_sms, json=payload_sms.model_dump(by_alias=True))
                logger.info(f"Status code: {response.status_code}")
                logger.info(f"Response content: {response.text}")
            # for slice in subscriber_model.snssai:
            #     single_nssai = Snssai(
            #         sst=SstConvertion.to_int(slice.sliceType),
            #         sd=str(int(slice.sliceId, 16))
            #     )
            #     if subscriber_model.imsi in self.base_model.blue_model_5g.ue_dict.keys():
            #         if single_nssai not in self.base_model.blue_model_5g.ue_dict[subscriber_model.imsi]:
            #             self.base_model.blue_model_5g.ue_dict[subscriber_model.imsi].append(single_nssai)
            #     else:
            #         self.base_model.blue_model_5g.ue_dict[subscriber_model.imsi] = []
            #         self.base_model.blue_model_5g.ue_dict[subscriber_model.imsi].append(single_nssai)
            #
            #     payload_sms = SessionManagementSubscriptionData(
            #         single_nssai=single_nssai
            #     )
            #     sub_slice = self.get_slice(slice.sliceId)
            #     for dnn in sub_slice.dnnList:
            #         sub_dnn = self.get_dnn(dnn)
            #         configuration = DnnConfiguration(
            #             s_ambr=SessionAmbr(
            #                 uplink=sub_dnn.uplinkAmbr.replace(" ", ""),
            #                 downlink=sub_dnn.downlinkAmbr.replace(" ", "")
            #             ),
            #             five_qosProfile=FiveQosProfile(
            #                 five_qi=sub_dnn.default5qi
            #             )
            #         )
            #         payload_sms.add_configuration(dnn, configuration)
            #         response = client.put(api_url_sms, json=payload_sms.model_dump(by_alias=True))
            #         logger.info(f"Status code: {response.status_code}")
            #         logger.info(f"Response content: {response.text}")

            return []

    def del_ues(self, subscriber_model: OAIDelSubscriberModel) -> list:
        """
        Calls OAI api to delete an existing UE and all his related SMS from DB.
        :param subscriber_model: imsi to delete.
        """
        logger.info(f"Try to delete user: {subscriber_model.imsi}")
        with httpx.Client(http1=False, http2=True) as client:
            api_url = f"http://{self.base_model.blue_model_5g.core_services.udr.external_ip[0]}:80/nudr-dr/v2/subscription-data/{subscriber_model.imsi}/authentication-data/authentication-subscription"
            response = client.delete(api_url)
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Response content: {response.text}")

        for sms in self.base_model.blue_model_5g.ue_dict[subscriber_model.imsi]:
            with httpx.Client(http1=False, http2=True) as client:
                api_url = f"http://{self.base_model.blue_model_5g.core_services.udr.external_ip[0]}:80/nudr-dr/v2/subscription-data/{subscriber_model.imsi}/{self.base_model.blue_model_5g.config.plmn}/provisioned-data/sm-data"
                response = client.delete(api_url, params={'sst': sms.sst, 'sd': sms.sd})
                logger.info(f"Status code: {response.status_code}")
                logger.info(f"Response content: {response.text}")

        del self.base_model.blue_model_5g.ue_dict[subscriber_model.imsi]
        return []

    def add_slice(self, add_slice_model: OAIAddSliceModel):
        """
        Add slice to the core and upf.
        If area is provided in OAIAddSliceModel then the core and upf will be restarted with all structure updated,
        otherwise the slice will be only added to "sliceProfiles".
        :param add_slice_model: slice to add.
        :return: day2 instruction to restart core and upf with new slice.
        """
        res = []
        logger.info(f"Try to add slice: {add_slice_model.sliceId}, {add_slice_model.sliceType}")
        add = self.add_slice_to_conf(add_slice_model)
        if add and add_slice_model.area_id is not None:
            core_config = copy.deepcopy(self.base_model.blue_model_5g.oai_config_values)
            upf_config = copy.deepcopy(self.base_model.blue_model_5g.upf_config_dict[add_slice_model.area_id])

            mcc = self.base_model.blue_model_5g.config.plmn[0:3]
            mnc = self.base_model.blue_model_5g.config.plmn[-2:]

            # Add SNSSAI
            new_snssai = self.add_snssai(core_config.currentconfig, add_slice_model.sliceId, add_slice_model.sliceType)

            self.add_snssai(upf_config, add_slice_model.sliceId, add_slice_model.sliceType)

            # Add plmn item
            self.add_plmn_item(core_config.currentconfig, mcc, mnc, add_slice_model.area_id, new_snssai)

            for dnn in add_slice_model.dnnList:
                dnn_item = DnnItem(
                    dnn=dnn
                )
                # Add dnns
                self.add_dnn_dnns(upf_config, dnn)
                self.add_dnn_dnns(core_config.currentconfig, dnn)

                # Add snssai upf/smf info list
                self.add_dnn_snssai_upf_info_list_item(upf_config, new_snssai, dnn_item)
                self.add_dnn_snssai_smf_info_list_item(core_config.currentconfig, new_snssai, dnn_item)

                # Add local subscription info
                self.add_local_subscription_info(core_config.currentconfig, new_snssai, dnn)

            upf_conf_yaml = yaml.dump(json.loads(upf_config.model_dump_json(by_alias=True)))

            # Save UPF conf
            self.base_model.blue_model_5g.upf_config_dict[add_slice_model.area_id] = upf_config
            # Save Core conf
            self.base_model.blue_model_5g.oai_config_values = core_config

            self.to_db()

            area = self.base_model.edge_areas[add_slice_model.area_id]
            upf_configurator = Configurator_OAI_UPF(area.nsd.descr.nsd.nsd[0].id, 1, self.get_id(),
                                                    ConfiguratorOAIUPFVars(
                                                        upf_id=add_slice_model.area_id,
                                                        nrf_ipv4_address=self.base_model.blue_model_5g.core_services.nrf.external_ip[0],
                                                        upf_conf=upf_conf_yaml
                                                    ))
            res += self.kdu_upgrade(self.base_model.core_area.nsd, json.loads(core_config.model_dump_json(by_alias=True)), self.KDU_NAME)
            res += upf_configurator.dump()
            res += self.reload_all_upf(add_slice_model.area_id)
            res += self.ran_day2_conf(self.base_model.ran_areas[add_slice_model.area_id])

        return res

    def del_slice(self, del_slice_model: OAIDelSliceModel):
        """
        Delete slice from the core and upf.
        If area is provided in OAIDelSliceModel then the core and upf will be restarted with all structure updated,
        otherwise the slice will be only delete from "sliceProfiles".
        :param del_slice_model: slice to delete.
        :return: day2 instruction to restart core and upf without deleted slice.
        """
        res = []
        logger.info(f"Try to del slice: {del_slice_model.sliceId}")

        sub_area = self.get_area_from_sliceid(del_slice_model.sliceId)
        sub_slice = self.get_slice(del_slice_model.sliceId)
        mcc = self.base_model.blue_model_5g.config.plmn[0:3]
        mnc = self.base_model.blue_model_5g.config.plmn[-2:]

        if sub_slice and sub_area is not None:
            core_config = copy.deepcopy(self.base_model.blue_model_5g.oai_config_values)
            upf_config = copy.deepcopy(self.base_model.blue_model_5g.upf_config_dict[sub_area.id])

            # Delete SNSSAI
            snssai = self.del_snssai(core_config.currentconfig, del_slice_model.sliceId)
            self.del_snssai(upf_config, del_slice_model.sliceId)

            # Delete plmn item
            self.del_plmn_item(core_config.currentconfig, mcc, mnc, sub_area.id, snssai)

            for dnn in sub_slice.dnnList:
                # Delete dnns
                # self.del_dnn_dnns(upf_config, dnn)
                # self.del_dnn_dnns(core_config.currentconfig, dnn)

                # Add local subscription info
                self.del_local_subscription_info(core_config.currentconfig, del_slice_model.sliceId, dnn)

            # Delete snssai upf/smf info list
            self.destroy_snssai_upf_info_list_item(upf_config, del_slice_model.sliceId)
            self.destroy_snssai_smf_info_list_item(core_config.currentconfig, del_slice_model.sliceId)

            upf_conf_yaml = yaml.dump(json.loads(upf_config.model_dump_json(by_alias=True)))

            # Save UPF conf
            self.base_model.blue_model_5g.upf_config_dict[sub_area.id] = upf_config
            # Save Core conf
            self.base_model.blue_model_5g.oai_config_values = core_config

            self.to_db()

            area = self.base_model.edge_areas[sub_area.id]
            upf_configurator = Configurator_OAI_UPF(area.nsd.descr.nsd.nsd[0].id, 1, self.get_id(),
                                                    ConfiguratorOAIUPFVars(
                                                        upf_id=area.id,
                                                        nrf_ipv4_address=self.base_model.blue_model_5g.core_services.nrf.external_ip[0],
                                                        upf_conf=upf_conf_yaml
                                                    ))
            res += self.kdu_upgrade(self.base_model.core_area.nsd, json.loads(core_config.model_dump_json(by_alias=True)), self.KDU_NAME)
            res += upf_configurator.dump()
            res += self.reload_all_upf(except_id=sub_area.id)
            res += self.ran_day2_conf(self.base_model.ran_areas[sub_area.id])

        # Update UE DB
        for imsi in self.base_model.blue_model_5g.ue_dict.keys():
            for ue_slice in self.base_model.blue_model_5g.ue_dict[imsi]:
                if del_slice_model.sliceId == ue_slice.sd:
                    self.base_model.blue_model_5g.ue_dict[imsi].remove(ue_slice)
                    if len(self.base_model.blue_model_5g.ue_dict[imsi]) == 0:
                        del self.base_model.blue_model_5g.ue_dict[imsi]
                        self.del_ues(imsi)

        self.del_slice_from_conf(sub_slice, sub_area)
        return res

    def add_tac(self, area: SubArea):
        """
        Create the new VM where UPF will run.
        :param area: new area to add.
        :return: day2 instruction to create new VM.
        """
        res = super().add_tac(area)
        return res

    def add_tac_day2(self, area: SubArea):
        """
        Call edge_day2_conf on new VM to configure it, then update core configuration to support new area.
        :param area: new area to configure.
        :return: day2 instruction to configure new VM and update core.
        """
        res = []
        temp = super().add_tac_day2(area)
        # Update core
        core_config = copy.deepcopy(self.base_model.blue_model_5g.oai_config_values)
        mcc = self.base_model.blue_model_5g.config.plmn[0:3]
        mnc = self.base_model.blue_model_5g.config.plmn[-2:]
        self.add_host_aliases(core_config.oai_smf, area.id)
        self.add_available_upf(core_config.currentconfig, area.id)
        for slice in area.slices:
            new_snssai = self.add_snssai(core_config.currentconfig, slice.sliceId, slice.sliceType)
            self.add_plmn_item(core_config.currentconfig, mcc, mnc, area.id, new_snssai)
            sub_slice = self.get_slice(slice.sliceId)
            for dnn in sub_slice.dnnList:
                dnn_item = DnnItem(
                    dnn=dnn
                )
                self.add_local_subscription_info(core_config.currentconfig, new_snssai, dnn)
                self.add_dnn_dnns(core_config.currentconfig, dnn)
                self.add_dnn_snssai_smf_info_list_item(core_config.currentconfig, new_snssai, dnn_item)

        self.base_model.blue_model_5g.oai_config_values = core_config

        self.to_db()

        res += self.kdu_upgrade(self.base_model.core_area.nsd, json.loads(core_config.model_dump_json(by_alias=True)), self.KDU_NAME)
        res += temp
        res += self.reload_all_upf(except_id=area.id)
        return res

    def del_tac_day2(self, area: SubArea):
        """
        Delete area from configuration and update the core.
        :param area: area to delete.
        :return: day2 instruction to delete area and update core.
        """
        res = []
        temp = super().del_tac_day2(area)
        core_config = copy.deepcopy(self.base_model.blue_model_5g.oai_config_values)
        self.del_host_aliases(core_config.oai_smf, area.id)
        self.del_available_upf(core_config.currentconfig, area.id)
        mcc = self.base_model.blue_model_5g.config.plmn[0:3]
        mnc = self.base_model.blue_model_5g.config.plmn[-2:]
        for slice in area.slices:
            del_snssai = self.del_snssai(core_config.currentconfig, slice.sliceId)
            self.destroy_plmn_list(core_config.currentconfig, mcc, mnc, area.id)
            sub_slice = self.get_slice(slice.sliceId)
            for dnn in sub_slice.dnnList:
                self.del_local_subscription_info(core_config.currentconfig, del_snssai.sd, dnn)
                # self.del_dnn_dnns(core_config.currentconfig, dnn)
                self.destroy_snssai_smf_info_list_item(core_config.currentconfig, del_snssai.sd)

        self.base_model.blue_model_5g.oai_config_values = core_config

        self.to_db()

        res += self.kdu_upgrade(self.base_model.core_area.nsd, json.loads(core_config.model_dump_json(by_alias=True)), self.KDU_NAME)
        res += temp
        res += self.reload_all_upf(except_id=area.id)
        return res
