import copy
from typing import *

from pydantic import Field

from blueprints.blue_5g_base.blueprint_5g_base_beta import Blue5GBaseBeta
from blueprints.blue_sdcore import sdcore_default_config
from blueprints.blue_sdcore.configurators.sdcore_upf_configurator import ConfiguratorSDCoreUpf, \
    ConfiguratorSDCoreUPFVars
from blueprints.blue_sdcore.sdcore_models import BlueSDCoreCreateModel
from blueprints.blue_sdcore.sdcore_values_model import SimAppYaml, SDCoreValuesModel
from models.base_model import NFVCLBaseModel
from models.blueprint.blueprint_base_model import BlueKDUConf, BlueVNFD, BlueNSD
from models.blueprint.rest_blue import BlueGetDataModel
from models.k8s.k8s_objects import K8sService
from models.vim.vim_models import VimNetMap, KubeDeploymentUnit, VirtualNetworkFunctionDescriptor, \
    VirtualDeploymentUnit, VMFlavors
from nfvo.nsd_manager_beta import Sol006NSDBuilderBeta, get_kdu_services, get_ns_vld_ip
from nfvo.osm_nbi_util import get_osm_nbi_utils
from nfvo.vnf_manager_beta import Sol006VnfdBuilderBeta
from utils.log import create_logger
from utils.persistency import DB

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
    upf_mgt_ip: Optional[str] = Field(default=None)
    upf_data_ip: Optional[str] = Field(default=None)
    upf_data_network_cidr: Optional[str] = Field(default=None)
    sdcore_config_values: Optional[SDCoreValuesModel] = Field(default=None)


class BlueSDCore(Blue5GBaseBeta):
    blue_model_5g: BlueSDCoreModel

    CHART_NAME = "nfvcl/sd-core"
    KDU_NAME = "sdcore"
    VNF_ID_SUFFIX = "sdcore"
    NS_ID_INFIX = "SDCORE"

    @classmethod
    def rest_create(cls, msg: BlueSDCoreCreateModel):
        return cls.api_day0_function(msg)

    @classmethod
    def day2_methods(cls):
        pass

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None) -> None:
        Blue5GBaseBeta.__init__(self, conf, id_, data=data, db=db, nbiutil=nbiUtil)

        logger.info("Creating BlueSDCore Blueprint")
        self.base_model.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [{'method': 'init_day2_conf'}],
                'dayN': []
            }]
        }
        self.blue_model_5g = BlueSDCoreModel.model_validate(self.base_model.conf)

        self.blue_model_5g.sdcore_config_values = copy.deepcopy(sdcore_default_config.default_config)
        self.blue_model_5g.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml = SimAppYaml()

        self.init_base()

    def bootstrap_day0(self, model_msg) -> list:
        return self.nsd()

    def core_vnfd(self, vls: List[VimNetMap]) -> List[BlueVNFD]:
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

    def core_nsd(self) -> List[str]:
        logger.info("Creating Core NSD(s)")

        vim_net_mapping1 = VimNetMap.build_vnm(
            "mgt",
            self.MGT_NETWORK_IF_NAME,
            self.networks_5g.mgt,
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

        vnfd_k8s = self.core_vnfd(vls=[vim_net_mapping1])

        kdu_config = BlueKDUConf(
            kdu_name=self.KDU_NAME,
            k8s_namespace=str(self.get_id()).lower(),
            additionalParams=self.blue_model_5g.sdcore_config_values.model_dump(exclude_none=True, by_alias=True)
        )

        nsd_id = f"{self.get_id()}_{self.NS_ID_INFIX}_{self.blue_model_5g.config.plmn}"

        n_obj = Sol006NSDBuilderBeta(
            vnfd_k8s,
            self.core_vim.name,
            nsd_id,
            "core",
            [vim_net_mapping1],
            knf_configs=[kdu_config]
        )

        nsd_item = n_obj.get_nsd()
        # TODO improve this
        self.base_model.nsd_.append(nsd_item)
        self.nsd_core = nsd_item
        self.to_db()
        return [nsd_id]

    def edge_vnfd(self, vls: List[VimNetMap]) -> List[BlueVNFD]:
        logger.info("Creating Edge VNFD(s)")
        created_vdu = VirtualDeploymentUnit.build_vdu(
            "upf",
            "sdcore-upf",
            list(map(lambda x: x.vim_net, vls[1:])),
            VMFlavors(vcpu_count="4", memory_mb="4096", storage_gb="16")
        )
        edge_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            f'{self.get_id()}_{self.VNF_ID_SUFFIX}_upf',
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

    def edge_nsd(self) -> List[str]:
        logger.info("Creating Edge NSD(s)")

        vim_net_mapping1 = VimNetMap.build_vnm(
            "mgt",
            self.MGT_NETWORK_IF_NAME,
            self.networks_5g.mgt,
            True
        )

        vim_net_mapping2 = VimNetMap.build_vnm(
            f"data_{self.networks_5g.wan}",
            self.WAN_NETWORK_IF_NAME,
            self.networks_5g.wan,
            False
        )

        vnfd_edge = self.edge_vnfd(vls=[vim_net_mapping1, vim_net_mapping2])

        nsd_id = f"{self.get_id()}_{self.NS_ID_INFIX}_{self.blue_model_5g.config.plmn}_upf"

        n_obj = Sol006NSDBuilderBeta(
            vnfd_edge,
            self.core_vim.name,
            nsd_id,
            "edge",
            [vim_net_mapping1, vim_net_mapping2]
        )

        nsd_item = n_obj.get_nsd()
        # TODO improve this
        self.base_model.nsd_.append(nsd_item)
        # self.nsd_core = nsd_item
        self.to_db()
        return [nsd_id]

    def core_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        """
        Used only to configure 5GC modules OpenStack VM (at the moment of this comment, it is only "UPF")
        :param arg:
        :param nsd_item:
        :return:
        """
        logger.info("Initializing Core Day2 configurations")
        res = []
        res += self.core_init_values_update(upf_ip=self.blue_model_5g.upf_data_ip)
        return res

    def core_init_values_update(self, upf_ip: str) -> list:
        # Load default configuration
        self.blue_model_5g.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml = copy.deepcopy(sdcore_default_config.default_config.omec_sub_provision.config.simapp.cfg_files.simapp_yaml)

        # Set upf ip
        self.blue_model_5g.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration.network_slices[0].site_info.upf.upf_name = upf_ip

        # Changing this value force a pod restart, this may be avoided changing the helm chart to add a new unused field inside the pod spec
        self.blue_model_5g.sdcore_config_values.omec_sub_provision.images.pull_policy = "Always"
        # TODO check if needed
        self.blue_model_5g.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.info.version = "2.0.0"

        # Convert the configuration in SD-Core format
        self.blue_model_5g.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration.from_generic_5g_model(self.blue_model_5g)

        return self.kdu_upgrade(self.nsd_core, self.blue_model_5g.sdcore_config_values.model_dump(exclude_none=True, by_alias=True), self.KDU_NAME)

    def edge_day2_conf(self, model_arg: dict, nsd_item: dict) -> list:
        logger.info("Initializing Edge Day2 configurations")
        res = []
        res += ConfiguratorSDCoreUpf(
            self.base_model.nsd_[1].descr.nsd.nsd[0].id, 1, self.get_id(),
            ConfiguratorSDCoreUPFVars(
                upf_data_cidr=self.blue_model_5g.upf_data_network_cidr,
                upf_internet_iface=self.MGT_NETWORK_IF_NAME
            )
        ).dump()
        return res

    def init_day2_conf(self, msg) -> list:
        logger.info("Initializing Day2 configurations")
        res = []
        res += self.core_day2_conf({}, {})
        res += self.edge_day2_conf({}, {})
        # Configurator_SDCore(self.base_model.nsd_[0].descr.nsd.nsd[0].id, 1, self.get_id(), {"webui_ip": self.blue_sdcore_model.core_services.webui.external_ip[0]}) #.dump()
        # res += self.core_upXade({})
        return res

    def get_ip(self) -> None:
        logger.info('Getting IP addresses of VNFIs (ext version)')
        super().get_ip()

    def get_ip_edge(self, ns: BlueNSD) -> None:
        logger.debug('Getting IPs for edge')
        vlds = get_ns_vld_ip(ns.nsi_id, ["mgt", f'data_{self.networks_5g.wan}'])
        self.blue_model_5g.upf_mgt_ip = vlds["mgt"][0]['ip']
        self.blue_model_5g.upf_data_ip = vlds[f'data_{self.networks_5g.wan}'][0]['ip']

        core_data_network = self.topology_get_network(self.networks_5g.wan)
        self.blue_model_5g.upf_data_network_cidr = str(core_data_network.cidr)

        logger.debug(f'MGT IP for edge: {self.blue_model_5g.upf_mgt_ip}')
        logger.debug(f'DATA IP for edge: {self.blue_model_5g.upf_data_ip}')
        logger.debug(f'DATA NETWORK CIDR for edge: {self.blue_model_5g.upf_data_network_cidr}')

    def get_ip_core(self, n: BlueNSD) -> None:
        """
        Set IP for 5G core k8s services (AMF, SMF, etc)
        """
        logger.debug('Getting Services IPs for core')
        try:
            kdu_services = get_kdu_services(n.nsi_id, self.KDU_NAME)
            kdu_services_dict = {}
            for kdu_service in kdu_services:
                kdu_services_dict[kdu_service.name] = kdu_service
            self.blue_model_5g.core_services = BlueSDCoreModelServices.model_validate(kdu_services_dict)
        except Exception as e:
            logger.exception("Exception in get_ip_core")
        # TODO need to be moved
        self.amf_ip = self.blue_model_5g.core_services.amf.external_ip[0]

    def pre_initialization_checks(self) -> bool:
        pass

    def get_data(self, get_request: BlueGetDataModel):
        pass

    def add_ues(self, msg: dict):
        pass

    def _destroy(self):
        # TODO to be implemented
        pass
