import copy
from typing import *
from nfvcl.blueprints.blue_5g_base.models.blue_5g_model import SubArea
from pydantic import Field
from nfvcl.blueprints.blue_5g_base.blueprint_5g_base_beta import Blue5GBaseBeta, EdgeArea5G, CoreArea5G, Area5GTypeEnum, RanArea5G, Blueprint5GBaseModel
from nfvcl.blueprints.blue_sdcore import sdcore_default_config
from nfvcl.blueprints.blue_sdcore.configurators.sdcore_upf_configurator import ConfiguratorSDCoreUpf, \
    ConfiguratorSDCoreUPFVars
from nfvcl.blueprints.blue_sdcore.rest_description import *
from nfvcl.blueprints.blue_sdcore.sdcore_models import BlueSDCoreCreateModel, BlueSDCoreAddSubscriberModel, BlueSDCoreDelSubscriberModel, BlueSDCoreAddSliceModel, BlueSDCoreDelSliceModel, BlueSDCoreAddTacModel, BlueSDCoreDelTacModel
from nfvcl.blueprints.blue_sdcore.sdcore_values_model import SimAppYaml, SDCoreValuesModel, NetworkSlice, DeviceGroup, GNodeB, SimAppYamlConfiguration
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint.blueprint_base_model import BlueKDUConf, BlueVNFD, BlueNSD
from nfvcl.models.blueprint.rest_blue import BlueGetDataModel
from nfvcl.models.k8s.k8s_objects import K8sService
from nfvcl.models.vim.vim_models import VimNetMap, KubeDeploymentUnit, VirtualNetworkFunctionDescriptor, \
    VirtualDeploymentUnit, VMFlavors
from nfvcl.nfvo.nsd_manager_beta import Sol006NSDBuilderBeta, get_kdu_services, get_ns_vld_model
from nfvcl.nfvo.osm_nbi_util import get_osm_nbi_utils
from nfvcl.nfvo.vnf_manager_beta import Sol006VnfdBuilderBeta
from nfvcl.utils.log import create_logger
from nfvcl.utils.persistency import DB

db = DB()
nbiUtil = get_osm_nbi_utils()
# create logger
logger = create_logger('BlueSDCore')


class BlueSDCoreModelServices(NFVCLBaseModel):
    amf: K8sService = Field()
    ausf: K8sService = Field()
    nrf: K8sService = Field()
    nssf: K8sService = Field()
    pcf: K8sService = Field()
    smf: K8sService = Field()
    udm: K8sService = Field()
    udr: K8sService = Field()

    simapp: K8sService = Field()
    metricfunc: K8sService = Field()
    webui: K8sService = Field()

    kafka: K8sService = Field()
    mongodb_arbiter_headless: K8sService = Field(alias="mongodb-arbiter-headless")


class BlueSDCoreModel(BlueSDCoreCreateModel):
    core_services: Optional[BlueSDCoreModelServices] = Field(default=None)
    sdcore_config_values: Optional[SDCoreValuesModel] = Field(default=None)


class BlueprintSdCoreBaseModel(Blueprint5GBaseModel):
    blue_model_5g: Optional[BlueSDCoreModel] = Field(default=None)


class BlueSDCore(Blue5GBaseBeta):
    CHART_NAME = "nfvcl/sdcore"
    KDU_NAME = "sdcore"
    VNF_ID_SUFFIX = "sdcore"
    NS_ID_INFIX = "SDCORE"
    UPF_IMAGE_NAME = "SDCore-UPF-v0.3.0"

    @property
    def config_ref(self) -> SimAppYamlConfiguration:
        return self.base_model.blue_model_5g.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration

    @classmethod
    def rest_create(cls, msg: BlueSDCoreCreateModel):
        return cls.api_day0_function(msg)

    @classmethod
    def rest_add_subscriber(cls, add_subscriber_model: BlueSDCoreAddSubscriberModel, blue_id: str):
        return cls.api_day2_function(add_subscriber_model, blue_id)

    @classmethod
    def rest_del_subscriber(cls, del_subscriber_model: BlueSDCoreDelSubscriberModel, blue_id: str):
        return cls.api_day2_function(del_subscriber_model, blue_id)

    @classmethod
    def rest_add_slice(cls, add_slice_model: BlueSDCoreAddSliceModel, blue_id: str):
        return cls.api_day2_function(add_slice_model, blue_id)

    @classmethod
    def rest_del_slice(cls, del_slice_model: BlueSDCoreDelSliceModel, blue_id: str):
        return cls.api_day2_function(del_slice_model, blue_id)

    @classmethod
    def rest_add_tac(cls, add_tac_model: BlueSDCoreAddTacModel, blue_id: str):
        return cls.api_day2_function(add_tac_model, blue_id)

    @classmethod
    def rest_del_tac(cls, del_tac_model: BlueSDCoreDelTacModel, blue_id: str):
        return cls.api_day2_function(del_tac_model, blue_id)

    @classmethod
    def day2_methods(cls):
        cls.api_router.add_api_route(
            path="/{blue_id}/add_tac",
            endpoint=cls.rest_add_tac,
            methods=["PUT"],
            description=ADD_TAC_DESCRIPTION,
            summary=ADD_TAC_DESCRIPTION
        )
        cls.api_router.add_api_route(
            path="/{blue_id}/del_tac",
            endpoint=cls.rest_del_tac,
            methods=["PUT"],
            description=DEL_TAC_DESCRIPTION,
            summary=DEL_TAC_DESCRIPTION
        )
        cls.api_router.add_api_route(
            path="/{blue_id}/add_slice",
            endpoint=cls.rest_add_slice,
            methods=["PUT"],
            description=ADD_SLICE_DESCRIPTION,
            summary=ADD_SLICE_DESCRIPTION
        )
        cls.api_router.add_api_route(
            path="/{blue_id}/del_slice",
            endpoint=cls.rest_del_slice,
            methods=["PUT"],
            description=DEL_SLICE_DESCRIPTION,
            summary=DEL_SLICE_DESCRIPTION
        )
        cls.api_router.add_api_route(
            path="/{blue_id}/add_subscriber",
            endpoint=cls.rest_add_subscriber,
            methods=["PUT"],
            description=ADD_SUBSCRIBER_DESCRIPTION,
            summary=ADD_SUBSCRIBER_DESCRIPTION
        )
        cls.api_router.add_api_route(
            path="/{blue_id}/del_subscriber",
            endpoint=cls.rest_del_subscriber,
            methods=["PUT"],
            description=DEL_SUBSCRIBER_DESCRIPTION,
            summary=DEL_SUBSCRIBER_DESCRIPTION
        )

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None) -> None:
        Blue5GBaseBeta.__init__(self, conf, id_, data=data, db=db, nbiutil=nbiUtil)
        logger.info("Creating BlueSDCore Blueprint")

        if data:
            logger.warning("Blueprint loaded from db, skipping init")
            self.base_model = BlueprintSdCoreBaseModel.model_validate(data)
        else:
            self.base_model = BlueprintSdCoreBaseModel.model_validate(self.base_model.model_dump())
            self.base_model.blue_model_5g = BlueSDCoreModel.model_validate(self.base_model.conf)

            self.base_model.blue_model_5g.sdcore_config_values = copy.deepcopy(sdcore_default_config.default_config)
            self.base_model.blue_model_5g.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml = SimAppYaml()

            self.init_base()

        self.base_model.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [{'method': 'init_day2_conf'}],
                'dayN': []
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
        }

    def bootstrap_day0(self, model_msg) -> list:
        return self.nsd()

    def core_vnfd(self, area: CoreArea5G, vls: List[VimNetMap]) -> List[BlueVNFD]:
        logger.info("Creating Core VNFD(s)")
        core_kdu = KubeDeploymentUnit.build_kdu(self.KDU_NAME, self.CHART_NAME, vls)
        core_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            f'{self.get_id()}_{self.VNF_ID_SUFFIX}',
            kdu_list=[core_kdu]
        )
        built_core_vnfd_package = Sol006VnfdBuilderBeta(core_vnfd)
        blue_vnfd = built_core_vnfd_package.get_vnf_blue_descr_only_kdu()
        self.base_model.vnfd.core.append(blue_vnfd)
        self.to_db()
        return [blue_vnfd]

    def core_nsd(self, area: CoreArea5G) -> List[str]:
        logger.info(f"Creating Core NSD in area {area.id}")

        vim_net_mapping1 = VimNetMap.build_vnm(
            "mgt",
            self.MGT_NETWORK_IF_NAME,
            self.base_model.networks_5g.mgt,
            True,
            "mgt_net"
        )

        # vim_net_mapping2 = VimNetMap.build_vnm(
        #     "data",
        #     self.WAN_NETWORK_IF_NAME,
        #     wan_network,
        #     False,
        #     "data_net"
        # )

        vnfd_k8s = self.core_vnfd(area, vls=[vim_net_mapping1])

        kdu_config = BlueKDUConf(
            kdu_name=self.KDU_NAME,
            k8s_namespace=str(self.get_id()).lower(),
            additionalParams=self.base_model.blue_model_5g.sdcore_config_values.model_dump_for_helm()
        )

        nsd_id = f"{self.get_id()}_{self.NS_ID_INFIX}_{self.base_model.blue_model_5g.config.plmn}"

        n_obj = Sol006NSDBuilderBeta(
            vnfd_k8s,
            self.base_model.core_vim.name,
            nsd_id,
            Area5GTypeEnum.CORE.value,
            [vim_net_mapping1],
            knf_configs=[kdu_config]
        )

        nsd_item = n_obj.get_nsd()
        nsd_item.area_id = area.id
        self.base_model.nsd_.append(nsd_item)
        area.nsd = nsd_item
        self.to_db()
        return [nsd_id]

    def edge_vnfd(self, area: EdgeArea5G, vls: List[VimNetMap]) -> List[BlueVNFD]:
        logger.info("Creating Edge VNFD(s)")
        created_vdu = VirtualDeploymentUnit.build_vdu(
            f"upf_{area.id}",
            self.UPF_IMAGE_NAME,
            list(map(lambda x: x.vim_net, vls[1:])),
            VMFlavors(vcpu_count="4", memory_mb="4096", storage_gb="16")
        )
        edge_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            f'{self.get_id()}_{self.VNF_ID_SUFFIX}_upf_{area.id}',
            "root",
            "root",
            cloud_init=True,
            vdu_list=[created_vdu]
        )
        built_core_vnfd_package = Sol006VnfdBuilderBeta(edge_vnfd, cloud_init=True, hemlflexcharm=True)
        blue_vnfd = built_core_vnfd_package.get_vnf_blue_descr_only_vdu()
        self.base_model.vnfd.area.append(blue_vnfd)
        self.to_db()

        return [blue_vnfd]

    def edge_nsd(self, area: EdgeArea5G) -> List[str]:
        logger.info(f"Creating Edge NSD in area {area.id}")

        vim = self.get_topology().get_vim_from_area_id_model(area.id)

        vim_net_mapping1 = VimNetMap.build_vnm(
            "mgt",
            self.MGT_NETWORK_IF_NAME,
            self.base_model.networks_5g.mgt,
            True
        )

        vim_net_mapping2 = VimNetMap.build_vnm(
            f"data_{self.base_model.networks_5g.wan}",
            self.WAN_NETWORK_IF_NAME,
            self.base_model.networks_5g.wan,
            False
        )

        vnfd_edge = self.edge_vnfd(area, vls=[vim_net_mapping1, vim_net_mapping2])

        nsd_id = f"{self.get_id()}_{self.NS_ID_INFIX}_{area.id}_{self.base_model.blue_model_5g.config.plmn}_upf"

        n_obj = Sol006NSDBuilderBeta(
            vnfd_edge,
            vim.name,
            nsd_id,
            Area5GTypeEnum.EDGE.value,
            [vim_net_mapping1, vim_net_mapping2]
        )

        nsd_item = n_obj.get_nsd()
        nsd_item.area_id = area.id
        self.base_model.nsd_.append(nsd_item)
        area.nsd = nsd_item
        self.to_db()
        return [nsd_id]

    def core_day2_conf(self, area: CoreArea5G) -> list:
        """
        Used only to configure 5GC modules OpenStack VM (at the moment of this comment, it is only "UPF")
        :param area:
        :return:
        """
        logger.info("Initializing Core Day2 configurations")
        res = []
        res += self.core_init_values_update()
        return res

    def core_init_values_update(self) -> list:
        # Load default configuration
        self.base_model.blue_model_5g.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml = copy.deepcopy(
            sdcore_default_config.default_config.omec_sub_provision.config.simapp.cfg_files.simapp_yaml)

        # Convert the requested configuration in SD-Core format
        self.config_ref.from_generic_5g_model(self.base_model.blue_model_5g)

        # Set UPFs ip
        # TODO need more checking, it may override the ip in some cases
        for area_for_slice in self.base_model.blue_model_5g.areas:
            for slice_in_area in area_for_slice.slices:
                # TODO check size, should be 1
                network_slice: NetworkSlice = list(filter(lambda x: x.slice_id.sd == slice_in_area.sliceId, self.config_ref.network_slices))[0]
                network_slice.site_info.upf.upf_name = self.base_model.edge_areas[self.base_model.edge_areas[area_for_slice.id].id].upf_data_ip

                # Set the ip pool in the edge area
                # TODO this only work with 1 device group
                device_group: DeviceGroup = list(filter(lambda x: x.name == network_slice.site_device_group[0], self.config_ref.device_groups))[0]
                self.base_model.edge_areas[self.base_model.edge_areas[area_for_slice.id].id].upf_ue_ip_pool = device_group.ip_domain_expanded.ue_ip_pool
                self.base_model.edge_areas[self.base_model.edge_areas[area_for_slice.id].id].upf_dnn = device_group.ip_domain_expanded.dnn

        # Changing this value force a pod restart, this may be avoided changing the helm chart to add a new unused field inside the pod spec
        self.base_model.blue_model_5g.sdcore_config_values.omec_sub_provision.images.pull_policy = "Always"
        # TODO check if needed
        self.base_model.blue_model_5g.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.info.version = "2.0.0"

        logger.debug("SENDING UPDATED CONFIGURATION TO K8S:")
        logger.debug("-------------------------------------")
        logger.debug(self.base_model.blue_model_5g.sdcore_config_values.model_dump_for_helm())
        logger.debug("-------------------------------------")

        return self.kdu_upgrade(self.base_model.core_area.nsd, self.base_model.blue_model_5g.sdcore_config_values.model_dump_for_helm(), self.KDU_NAME)

    def edge_day2_conf(self, area: EdgeArea5G) -> list:
        logger.info("Initializing Edge Day2 configurations")
        res = []
        res += ConfiguratorSDCoreUpf(
            area.nsd.descr.nsd.nsd[0].id, 1, self.get_id(),
            ConfiguratorSDCoreUPFVars(
                upf_data_cidr=area.upf_data_network_cidr,
                upf_internet_iface=self.MGT_NETWORK_IF_NAME,
                upf_ue_ip_pool=area.upf_ue_ip_pool,
                upf_dnn=area.upf_dnn
            )
        ).dump()
        return res

    def get_additional_ran_conf(self, area: RanArea5G) -> dict:
        additional_config = {
            'disable_offloading': self.WAN_NETWORK_IF_NAME,
            'additional_ip_route': f"192.168.252.0/24 via {self.base_model.edge_areas[area.id].upf_data_ip} dev {self.WAN_NETWORK_IF_NAME}"
        }
        return additional_config

    def get_ip(self) -> None:
        logger.info('Getting IP addresses of VNFIs (ext version)')
        super().get_ip()

    def get_ip_edge(self, ns: BlueNSD) -> None:
        logger.debug(f'Getting IPs for edge area {ns.area_id}')
        vlds = get_ns_vld_model(ns.nsi_id, ["mgt", f'data_{self.base_model.networks_5g.wan}'])

        self.base_model.edge_areas[ns.area_id].upf_mgt_ip = vlds["mgt"][0].get_ip_list_str()[0]
        self.base_model.edge_areas[ns.area_id].upf_data_ip = vlds[f'data_{self.base_model.networks_5g.wan}'][0].get_ip_list_str()[0]

        core_data_network = self.topology_get_network(self.base_model.networks_5g.wan)
        self.base_model.edge_areas[ns.area_id].upf_data_network_cidr = str(core_data_network.cidr)

        logger.debug(f'MGT IP for edge: {self.base_model.edge_areas[ns.area_id].upf_mgt_ip}')
        logger.debug(f'DATA IP for edge: {self.base_model.edge_areas[ns.area_id].upf_data_ip}')
        logger.debug(f'DATA NETWORK CIDR for edge: {self.base_model.edge_areas[ns.area_id].upf_data_network_cidr}')
        logger.debug(f'END Getting IPs for edge area {ns.area_id}')

    def get_ip_core(self, ns: BlueNSD) -> None:
        """
        Set IP for 5G core k8s services (AMF, SMF, etc)
        """
        logger.debug('Getting Services IPs for core')
        try:
            kdu_services = get_kdu_services(ns.nsi_id, self.KDU_NAME)
            kdu_services_dict = {}
            for kdu_service in kdu_services:
                kdu_services_dict[kdu_service.name] = kdu_service
            self.base_model.blue_model_5g.core_services = BlueSDCoreModelServices.model_validate(kdu_services_dict)
        except Exception as e:
            logger.exception("Exception in get_ip_core")
        # TODO need to be moved
        self.base_model.core_area.amf_ip = self.base_model.blue_model_5g.core_services.amf.external_ip[0]

    def pre_initialization_checks(self) -> bool:
        pass

    def get_data(self, get_request: BlueGetDataModel):
        pass

    def _destroy(self):
        # TODO to be implemented
        pass

    def update_core(self):
        """
        Save the current configuration to the db and update the core
        """
        self.to_db()
        return self.kdu_upgrade(self.base_model.core_area.nsd, self.base_model.blue_model_5g.sdcore_config_values.model_dump_for_helm(), self.KDU_NAME)

    def add_ues(self, subscriber_model: BlueSDCoreAddSubscriberModel) -> list:
        logger.info(f"Adding UE with IMSI: {subscriber_model.imsi}")
        self.config_ref.add_subscriber_from_generic_model(subscriber_model)
        return self.update_core()

    def del_ues(self, subscriber_model: BlueSDCoreDelSubscriberModel) -> list:
        logger.info(f"Deleting UE with IMSI: {subscriber_model.imsi}")
        self.config_ref.delete_subscriber(subscriber_model.imsi)
        return self.update_core()

    def add_slice(self, add_slice_model: BlueSDCoreAddSliceModel) -> list:
        logger.info(f"Adding Slice with ID: {add_slice_model.sliceId}")
        network_slice = self.config_ref.add_slice_from_generic_model(add_slice_model, add_slice_model.area_id)
        network_slice.site_info.upf.upf_name = self.base_model.edge_areas[self.base_model.edge_areas[add_slice_model.area_id].id].upf_data_ip
        # TODO add the slice to gnb
        return self.update_core()

    def del_slice(self, del_slice_model: BlueSDCoreDelSliceModel) -> list:
        logger.info(f"Deleting Slice with ID: {del_slice_model.sliceId}")
        self.config_ref.delete_slice(del_slice_model.sliceId)
        return self.update_core()

    def get_slices_for_area(self, area: SubArea):
        """
        Returns list of network slices in given area
        Args:
            area: Area to get slices for

        Returns: Slices found

        """
        network_slices_to_ret: List[NetworkSlice] = []

        for slice_in_area in area.slices:
            network_slices: List[NetworkSlice] = list(filter(lambda x: x.slice_id.sd == slice_in_area.sliceId, self.config_ref.network_slices))

            if len(network_slices) == 0:
                raise Exception("No network slice for this area")

            network_slices_to_ret.append(network_slices[0])

        return network_slices_to_ret

    def add_tac(self, area: SubArea):
        res = super().add_tac(area)

        for network_slice in self.get_slices_for_area(area):
            network_slice.site_info.g_node_bs = [GNodeB(name=f"gnb{area.id}", tac=area.id)]
            network_slice.site_info.upf.upf_name = self.base_model.edge_areas[self.base_model.edge_areas[area.id].id].upf_data_ip

            # Set the ip pool in the edge area
            # TODO this only work with 1 device group
            device_group: DeviceGroup = list(filter(lambda x: x.name == network_slice.site_device_group[0], self.config_ref.device_groups))[0]
            self.base_model.edge_areas[self.base_model.edge_areas[area.id].id].upf_ue_ip_pool = device_group.ip_domain_expanded.ue_ip_pool
            self.base_model.edge_areas[self.base_model.edge_areas[area.id].id].upf_dnn = device_group.ip_domain_expanded.dnn

        return res

    def add_tac_day2(self, area: SubArea):
        res = super().add_tac_day2(area)

        for network_slice in self.get_slices_for_area(area):
            network_slice.site_info.upf.upf_name = self.base_model.edge_areas[self.base_model.edge_areas[area.id].id].upf_data_ip

        # The configuration is updated in add_tac and sent to the core here
        res += self.update_core()
        return res

    def del_tac_day2(self, area: SubArea):
        res = super().del_tac_day2(area)

        for network_slice in self.get_slices_for_area(area):
            network_slice.site_info.g_node_bs = []
            network_slice.site_info.upf.upf_name = "PLACEHOLDER"

        res += self.update_core()
        return res
