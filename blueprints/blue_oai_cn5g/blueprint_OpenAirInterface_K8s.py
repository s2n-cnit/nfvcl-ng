import copy
from typing import List, Union, Dict

from blueprints.blue_5g_base.blueprint_5g_base_beta import Blue5GBaseBeta
from blueprints.blue_oai_cn5g.configurator.upf_configurator import Configurator_OAI_UPF
from blueprints.blue_oai_cn5g.models import OAIBlueCreateModel
from blueprints.blue_oai_cn5g.models.blue_OAI_k8s_model import OAIModel, OAIModelServices
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
from blueprints.blue_oai_cn5g.config.configurator import default_config

db = DB()
nbiUtil = get_osm_nbi_utils()
logger = create_logger('OpenAirInterface')

edge_vnfd_type = ['upf']

charts_list = ["mysql:8.0.31",
               "oai-nssf:v1.5.1",
               "oai-nrf:v1.5.1",
               "oai-udr:v1.5.1",
               "oai-udm:v1.5.1",
               "oai-ausf:v1.5.1",
               "oai-amf:v1.5.1",
               "oai-smf:v1.5.1"]

chartnames = ["mysql", "oai-nssf", "oai-nrf", "oai-udr", "oai-udm", "oai-ausf", "oai-amf", "oai-smf"]


# "oai-nrf:v1.5.1","mysql:8.0.31","oai-nssf:v1.5.1"
# ,"oai-nrf:v1.5.1"
class OpenAirInterface_K8s(Blue5GBaseBeta):
    oai_model: OAIModel

    @classmethod
    def rest_create(cls, msg: OAIBlueCreateModel):
        return cls.api_day0_function(msg)

    @classmethod
    def day2_methods(cls):
        pass

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None) -> None:
        Blue5GBaseBeta.__init__(self, conf, id_, data=data, db=db, nbiutil=nbiUtil)
        self.edge_nsd_id = None
        self.nsd_core = None
        self.upf_ip = None
        logger.info("Creating \"OpenAirInterface\" Blueprint")
        self.base_model.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}
                         # {'method': 'bootstrap_day0_1'},
                         # {'method': 'bootstrap_day0_2'},
                         # {'method': 'bootstrap_day0_3'},
                         # {'method': 'bootstrap_day0_4'},
                         # {'method': 'bootstrap_day0_5'},
                         # {'method': 'bootstrap_day0_6'},
                         # {'method': 'bootstrap_day0_7'},
                         # {'method': 'bootstrap_day0_8'}
                         ],
                'day2': [{'method': 'init_day2_conf'}],
                'dayN': []
            }]
            # 'add_tac': [{
            #     'day0': [{'method': 'add_tac_nsd'}],
            #     'day2': [{'method': 'add_tac_conf'}],
            #     'dayN': []
            # }],
            # 'del_tac': [{
            #     'day0': [],
            #     'day2': [{'method': 'del_tac_conf'}],
            #     'dayN': [{'method': 'del_tac_nsd'}]
            # }],
            # 'add_ues': [{
            #     'day0': [],
            #     'day2': [{'method': 'add_ues'}],
            #     'dayN': []
            # }],
            # 'del_ues': [{
            #     'day0': [],
            #     'day2': [{'method': 'del_ues'}],
            #     'dayN': []
            # }],
            # 'add_slice': [{
            #     'day0': [],
            #     'day2': [{'method': 'add_slice'}],
            #     'dayN': []
            # }],
            # 'del_slice': [{
            #     'day0': [],
            #     'day2': [{'method': 'del_slice'}],
            #     'dayN': []
            # }],
            # 'update_core': [{
            #     'day0': [],
            #     'day2': [{'method': 'core_upXade'}],
            #     'dayN': []
            # }],
            # 'add_ext': [{
            #     'day0': [{'method': 'add_ext_nsd'}],
            #     'day2': [{'method': 'add_ext_conf'}],
            #     'dayN': []
            # }],
            # 'del_ext': [{
            #     'day0': [],
            #     'day2': [],
            #     'dayN': [{'method': 'del_ext_conf'}]
            # }],
            # 'monitor': [{
            #     'day0': [],
            #     'day2': [{'method': 'enable_prometheus'}],
            #     'dayN': []
            # }],
            # 'log': [{
            #     'day0': [],
            #     'day2': [{'method': 'enable_elk'}],
            #     'dayN': []
            # }],
        }
        self.oai_model = OAIModel.model_validate(self.base_model.conf)
        # self.primitives = []
        # if "core" not in self.vnfd or "area" not in self.vnfd:
        #    self.vnfd = {'core': [], 'area': []}
        # if "running_free5gc_configuration" not in self.conf:
        #     self.conf["running_free5gc_configuration"] = free5GC_default_config.default_config
        # self.userManager = Configurator_Free5GC_User(self.conf)
        # self.coreManager = Configurator_Free5GC_Core(self.conf["running_free5gc_configuration"], self.conf)
        # "msg" is used if day0 modified the msg and day2 need to use the modified version of the message
        # It is a dict where every node is in the form {"operation": "message"}, ex: {"add_slice": "...message..."}
        self.msg = dict()

    def bootstrap_day0(self, model_msg) -> list:
        return self.nsd()

    def core_vnfd(self, vls: List[VimNetMap]) -> List[BlueVNFD]:
        # I have multiple vnf
        for chartname in chartnames:
            core_kdu = KubeDeploymentUnit.build_kdu(
                name=chartname,
                helm_chart=f'nfvcl/{chartname}',
                interface=vls
            )
            core_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
                vnf_id=f'{self.get_id()}_oai5g_{chartname}',
                kdu_list=[core_kdu]
            )
            build_core_vnfd_package = Sol006VnfdBuilderBeta(core_vnfd)
            blue_vnfd = build_core_vnfd_package.get_vnf_blue_descr_only_kdu()
            self.base_model.vnfd.core.append(blue_vnfd)
        self.to_db()
        return []

    def edge_vnfd(self, vls: List[VimNetMap]) -> List[BlueVNFD]:
        edge_vdu = VirtualDeploymentUnit.build_vdu(
            vdu_id=f'{self.get_id()}_upf_oai5g',
            vdu_image='UPF_OpenAirInterface5G',
            vdu_data_int_list=list(map(lambda x: x.vim_net, vls[1:])),  # Skip first net, mgt
            # vdu_flavor=VMFlavors(memory_mb="12288", storage_gb="32", vcpu_count="8")
            # vdu_data_int_list=list(map(lambda x: x.vim_net, vls))
        )
        edge_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            vnf_username="root",
            vnf_passwd="root",
            cloud_init=True,
            vnf_id=f'{self.get_id()}_UPF_OAI5G',
            vdu_list=[edge_vdu]
        )
        build_edge_vnfd_package = Sol006VnfdBuilderBeta(edge_vnfd, cloud_init=True, hemlflexcharm=True)
        blue_vnfd = build_edge_vnfd_package.get_vnf_blue_descr_only_vdu()
        self.base_model.vnfd.area.append(blue_vnfd)
        self.to_db()
        return []

    def core_nsd(self) -> List[str]:
        logger.info("Creating Core NSD(s)")

        core_vim: VimModel = self.get_topology().get_vim_from_area_id_model(0)

        if self.oai_model.config["network_endpoints"]["wan"] in core_vim.networks:
            wan_net = self.oai_model.config["network_endpoints"]["wan"]
            mgt_net = self.oai_model.config["network_endpoints"]["mgt"]
        else:
            raise ValueError("No networks found in VIM")

        vim_net_mapping = VimNetMap.build_vnm(
            "mgt",
            "ens3",
            mgt_net,
            True,
            "data_net"
        )

        # vim_net_mapping2 = VimNetMap.build_vnm(
        #     "data",
        #     "ens4",
        #     wan_net,
        #     False,
        #     "data_net"
        # )

        self.core_vnfd(vls=[vim_net_mapping])
        kdus_config_list: List[BlueKDUConf] = []

        for vnf in self.base_model.vnfd.core:
            chartname = vnf.name.split("_")[-1]
            kdus_config_list.append(BlueKDUConf(
                kdu_name=chartname,
                k8s_namespace=str(self.get_id().lower()),
                additionalParams=default_config[f'{chartname}']
                # sono parametri addizionali per il file dei chart
                # Posso per esempio settarmi l'alias dell'UPF nel chart NRF
            ))

        nsd_id = f"{self.get_id()}_OAI5G_{self.oai_model.config['plmn']}"

        n_obj = Sol006NSDBuilderBeta(
            vnfds=self.base_model.vnfd.core,
            vim_name=core_vim.name,
            nsd_id=nsd_id,
            nsd_type="core",
            vl_maps=[vim_net_mapping],
            knf_configs=kdus_config_list
        )

        self.nsd_core = n_obj.get_nsd()
        self.base_model.nsd_.append(self.nsd_core)
        self.to_db()
        return [nsd_id]

    def edge_nsd(self) -> List[str]:
        logger.info("Creating Edge NSD(s)")

        edge_vim: VimModel = self.get_topology().get_vim_from_area_id_model(0)

        if self.oai_model.config["network_endpoints"]["wan"] in edge_vim.networks:
            wan_net = self.oai_model.config["network_endpoints"]["wan"]
            mgt_net = self.oai_model.config["network_endpoints"]["mgt"]
        else:
            raise ValueError("No networks found in VIM")

        vim_net_mapping = VimNetMap.build_vnm(
            "mgt",
            "ens3",
            mgt_net,
            True,
            "data_net"
        )

        vim_net_mapping2 = VimNetMap.build_vnm(
            f"data_davide-net", #TODO leggere da config
            "ens4",
            wan_net,
            False,
            "data_net"
        )

        self.edge_vnfd(vls=[vim_net_mapping, vim_net_mapping2])

        self.edge_nsd_id = f"{self.get_id()}_UPF_OAI5G_{self.oai_model.config['plmn']}"

        n_obj = Sol006NSDBuilderBeta(
            vnfds=self.base_model.vnfd.area,
            vim_name=edge_vim.name,
            nsd_id=self.edge_nsd_id,
            nsd_type="edge",  # TODO Chiedere
            vl_maps=[vim_net_mapping, vim_net_mapping2]
        )

        nsd_item = n_obj.get_nsd()
        self.base_model.nsd_.append(nsd_item)
        self.to_db()
        return [self.edge_nsd_id]

    # def core_day2_conf(self, arg: dict, nsd_item: dict) -> list:
    #     res = []
    #     return res

    def edge_day2_conf(self, arg: dict, nsd_item: dict) -> List[str]:
        res = []
        return res

    def get_ip_core(self, n: BlueNSD) -> None:
        kdu_services_dict = {}
        try:
            for chartname in chartnames:
                kdu_services = get_kdu_services(n.nsi_id, chartname)
                for kdu_service in kdu_services:
                    kdu_services_dict[kdu_service.name] = kdu_service
                # Trasforma il dizionario nell'oggetto della classe (nello specifico OAIModelServices)
            self.oai_model.core_services = OAIModelServices.model_validate(kdu_services_dict)
        except Exception as e:
            logger.exception("Exception in get_ip_core")

    def get_ip_edge(self, n: BlueNSD) -> None:
        try:
            ip_dict = get_ns_vld_ip(n.nsi_id, list(map(lambda x: x.name, n.deploy_config.vld)))
            self.upf_ip = ip_dict['data_davide-net'][0]['ip']
        except Exception as e:
            logger.exception("Exception in get_ip_edge")
        pass

    def _destroy(self):
        pass

    def get_ip(self) -> None:
        super().get_ip()

    def add_ues(self, msg: dict):
        """

        :param msg:
        :return:
        """
        pass

    def pre_initialization_checks(self) -> bool:
        pass

    def get_data(self, get_request: BlueGetDataModel):
        pass

    def core_upXade(self, msg: dict) -> list:
        """

        :param msg:
        :return:
        """
        new_config = copy.deepcopy(default_config)
        new_config["oai-smf"]["hostAliases"]["ip"] = self.upf_ip
        new_config["oai-smf"]["hostAliases"]["hostnames"] = "spgwu.external"
        # default_config["oai-smf"] = new_config["oai-smf"]
        # new_config["omec-sub-provision"]["config"]["simapp"]["cfgFiles"]["simapp.yaml"]["info"]["version"] = "2.0.0"
        # new_config["omec-sub-provision"]["config"]["simapp"]["cfgFiles"]["simapp.yaml"]["configuration"]["subscribers"].append(
        #     {
        #         "ueId-start": "999930100007487",
        #         "ueId-end": "999930100007500",
        #         "plmnId": "20893",
        #         "opc": "981d464c7c52eb6e5036234984ad0bcf",
        #         "op": "",
        #         "key": "5122250214c33e723a5dd523fc145fc0",
        #         "sequenceNumber": "16f3b3f70fc2"
        #     }
        # )
        return self.kdu_upgrade(self.nsd_core, new_config["oai-smf"], "oai-smf", str(chartnames.index('oai-smf') + 1))

    def kdu_upgrade(self, nsd: BlueNSD, conf_params: dict, kdu_name: str, vnf_id: str):
        # TODO serve a qualcosa?
        # if 'kdu_model' not in conf_params:
        #     conf_params['kdu_model'] = self.CHART_NAME

        res = [
            {
                # TODO ci vuole il nome, altro modo per ottenerlo? dovrebbe essere lo stesso di nsd_id?
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

    def upf_config(self, model_arg: dict, nsd_item: dict) -> list:
        # self.oai_model.core_services.nrf.external_ip[0]
        res = []
        upf_configurator = Configurator_OAI_UPF(self.edge_nsd_id, 1, self.get_id(),{'ip' : self.oai_model.core_services.nrf.external_ip[0], 'interface' : 'ens4'})
        res += upf_configurator.dump()
        return res

    def core_day2_conf(self, arg: dict, nsd_item: dict) -> list:

        logger.info("Initializing Core Day2 configurations")
        res = []
        res += self.core_upXade({})
        return res

    def init_day2_conf(self, msg) -> list:
        logger.info("Initializing Day2 configurations")
        res = []
        res += self.core_day2_conf({}, {})
        res += self.upf_config({}, {})
        # Configurator_SDCore(self.base_model.nsd_[0].descr.nsd.nsd[0].id, 1, self.get_id(), {"webui_ip": self.blue_sdcore_model.core_services.webui.external_ip[0]}) #.dump()
        # res += self.core_upXade({})
        return res
