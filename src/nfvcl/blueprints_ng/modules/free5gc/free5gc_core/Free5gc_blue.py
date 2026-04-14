import copy
import random
import string
from typing import Optional, Dict, List, Tuple

from pydantic import Field

from nfvcl.blueprints_ng.modules.free5gc import free5gc_default_core_config, free5gc_subscriber_config
from nfvcl.blueprints_ng.modules.free5gc.free5gc_upf.Free5gcUpf_blue import FREE5GC_UPF_BLUE_TYPE
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_k8s import Generic5GK8sBlueprintNGState, Generic5GK8sBlueprintNG
from nfvcl_common.utils.log import create_logger
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.core5g.common import Create5gModel, SubArea, NetworkEndPointType
from nfvcl_models.blueprint_ng.free5gc.free5gcCore import Free5gcCoreConfig, Snssai, Free5gcSubScriber
from nfvcl_models.blueprint_ng.g5.core import Core5GDelTacModel, Core5GAddTacModel, Core5GDelSliceModel, Core5GAddSliceModel, Core5GDelSubscriberModel, Core5GAddSubscriberModel, NF5GType

FREE5GC_CORE_BLUE_TYPE = "free5gc"
free5gc_credentials = {"username": "admin", "password": "free5gc"}
logger = create_logger('Free5gc')


class Free5gcBlueCreateModel(Create5gModel):
    type: str = FREE5GC_CORE_BLUE_TYPE


class Free5gcBlueprintNGState(Generic5GK8sBlueprintNGState):
    """
    This class represent the current state of the blueprint, the data contained in this class will be saved to the DB.

    Every Resource should be stored in a variable in this class to be able to access it after the initial creation.

    Everything in this class should be serializable by Pydantic.

    Every field need to be Optional because the state is created empty.

    """
    free5gc_config_values: Optional[Free5gcCoreConfig] = Field(default=None)

    mcc: Optional[str] = Field(default=None)
    mnc: Optional[str] = Field(default=None)

    smf_ip: Optional[str] = Field(default=None)
    webui_ip: Optional[str] = Field(default=None)
    base_webui_api: Optional[str] = Field(default=None)

    nsi_nssf_id: int = Field(default=1)
    gnb_id: int = Field(default=0)
    supported_nssai_availability_nssf_id: int = Field(default=1)

    gpsis: List[str] = Field(default_factory=list)
    subscribers: List[Free5gcSubScriber] = Field(default_factory=list)


@blueprint_type(FREE5GC_CORE_BLUE_TYPE)
class Free5gc(Generic5GK8sBlueprintNG[Free5gcBlueprintNGState, Free5gcBlueCreateModel]):
    default_upf_implementation = FREE5GC_UPF_BLUE_TYPE

    def __init__(self, blueprint_id: str, state_type: type[Generic5GK8sBlueprintNGState] = Free5gcBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB.

        """
        super().__init__(blueprint_id, state_type)

    def network_functions_dictionary(self) -> Dict[NF5GType, Tuple[str, str]]:
        return {
            NF5GType.AMF: ("amf", "free5gc-free5gc-amf-amf-n2") if self.state.free5gc_config_values.global_.amf.service.ngap.enabled else ("amf", "free5gc-free5gc-amf-service"),
            NF5GType.AUSF: ("ausf", "free5gc-free5gc-ausf-service"),
            NF5GType.NRF: ("nrf", "nrf-nnrf"),
            NF5GType.SMF: ("smf", "free5gc-free5gc-smf-service"),
            NF5GType.UDM: ("udm", "free5gc-free5gc-udm-service"),
            NF5GType.UDR: ("udr", "free5gc-free5gc-udr-service"),
            NF5GType.NSSF: ("nssf", "free5gc-free5gc-nssf-service"),
            NF5GType.PCF: ("pcf", "free5gc-free5gc-pcf-service"),
            NF5GType.WEBUI: ("webui", "webui-service")
        }

    def wait_core_ready(self):
        pass

    def create_5g(self, create_model: Create5gModel):
        self.logger.info("Starting creation of Free5gc blueprint")

        core_area: SubArea = list(filter(lambda x: x.core, create_model.areas))[0]

        self.state.free5gc_config_values = copy.deepcopy(free5gc_default_core_config.default_core_config)

        self.state.core_helm_chart = HelmChartResource(
            area=core_area.id,
            name="free5gc",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/free5gc-4.0.0.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.core_helm_chart)

        self.state.mcc = create_model.config.plmn[0:3]
        self.state.mnc = create_model.config.plmn[-2:]

        self.update_core_values()

        self.provider.install_helm_chart(
            self.state.core_helm_chart,
            self.state.free5gc_config_values.model_dump(exclude_none=True, by_alias=True)
        )

        self.update_k8s_network_functions()
        if self.state.network_endpoints.n4 is None:
            self.state.smf_ip = self.state.k8s_network_functions[NF5GType.SMF].service.external_ip[0]
        self.state.webui_ip = self.state.k8s_network_functions[NF5GType.WEBUI].service.external_ip[0]

        self.state.base_webui_api = f"http://{self.state.webui_ip}:5000/api"

        self.update_core()
        # if self.state.network_endpoints.n4:
        #     self.provider.restart_deployment(self.state.core_helm_chart, self.state.core_helm_chart.deployments['smf'].name)

        for subscriber in create_model.config.subscribers.copy():
            self.add_ues(subscriber)

    def clear_core_values(self) -> None:
        """
        Clear all core data from configuration

        """
        self.state.free5gc_config_values.clear_core_values()

        #### ID Reset ####
        self.state.nsi_nssf_id = 1
        self.state.supported_nssai_availability_nssf_id = 1

    def update_core_values(self):
        self.clear_core_values()

        # TODO this should also disable the cert-pvc
        self.state.free5gc_config_values.mongodb.persistence.enabled = self.state.current_config.config.persistence.enabled
        self.state.free5gc_config_values.global_.cert = self.state.current_config.config.persistence.enabled
        self.state.free5gc_config_values.global_.nrf.service.type = "LoadBalancer"
        # TODO this value is not present in the current config
        # self.state.free5gc_config_values.mongodb.persistence.storageClass = self.state.current_config.config.persistence.storageClass

        if self.state.network_endpoints.n2 and self.state.network_endpoints.n2.type == NetworkEndPointType.MULTUS:
            self.state.free5gc_config_values.global_.n2network.set_multus(True, self.state.network_endpoints.n2.multus)
            self.state.free5gc_config_values.global_.amf.service.ngap.enabled = False
            self.state.free5gc_config_values.set_amf_ip(self.state.network_endpoints.n2.multus.ip_address.exploded)
        else:
            self.state.free5gc_config_values.global_.amf.service.ngap.enabled = True

        if self.state.network_endpoints.n4 and self.state.network_endpoints.n4.type == NetworkEndPointType.MULTUS:
            self.state.free5gc_config_values.global_.n4network.set_multus(True, self.state.network_endpoints.n4.multus)
            self.state.free5gc_config_values.set_smf_ip(self.state.network_endpoints.n4.multus.ip_address.exploded)
        else:
            self.state.free5gc_config_values.free5gc_smf.smf.service.type = "LoadBalancer"
            self.state.free5gc_config_values.set_smf_ip("0.0.0.0")

        if self.state.smf_ip:
            self.state.free5gc_config_values.set_smf_ip(self.state.smf_ip)

        self.state.free5gc_config_values.set_default_nrf_plmnd(self.state.mcc, self.state.mnc)
        self.state.free5gc_config_values.add_item_amf_servedGuamiList(self.state.mcc, self.state.mnc)
        self.state.free5gc_config_values.add_plmn_smf_item(self.state.mcc, self.state.mnc)
        self.state.free5gc_config_values.add_plmn_ausf_item(self.state.mcc, self.state.mnc)
        self.state.free5gc_config_values.add_supported_plmn_nssf(self.state.mcc, self.state.mnc)

        for sub_area in self.state.current_config.areas:
            upf_list = self.state.edge_areas[str(sub_area.id)].upf.upf_list
            if not upf_list:
                continue
            deployed_upf_info = upf_list[0]
            self.state.free5gc_config_values.add_item_amf_supportTaiList(self.state.mcc, self.state.mnc, f"{sub_area.id:x}".zfill(6))

            for sub_slice in sub_area.slices:
                _slice = Snssai(
                    sst=sub_slice.sliceType,
                    sd=sub_slice.sliceId
                )
                self.state.free5gc_config_values.add_plmn_amf_item(self.state.mcc, self.state.mnc, sub_area.id, _slice)
                self.state.free5gc_config_values.add_supportedsnssailist_item_nssf(self.state.mcc, self.state.mnc, _slice)
                self.state.free5gc_config_values.add_nsi_list_item_nssf(sub_slice.sliceType, sub_slice.sliceId, self.state.nsi_nssf_id)
                self.state.nsi_nssf_id = self.state.nsi_nssf_id + 1
                # self.state.free5gc_config_values.add_supported_nssai_nssf(self.state.supported_nssai_availability_nssf_id, self.state.mcc, self.state.mnc, str(sub_area.id).zfill(6), _slice)
                self.state.supported_nssai_availability_nssf_id = self.state.supported_nssai_availability_nssf_id + 1
                self.state.free5gc_config_values.add_tai_supportedsnssailist_nssf_item(self.state.mcc, self.state.mnc, f"{sub_area.id:x}".zfill(6), _slice)

                dnn_slice = self.state.current_config.get_slice_profile(_slice.sd)
                if dnn_slice is None:
                    raise ValueError(f"Slice profile not found for SD: {_slice.sd}")
                for dnn in dnn_slice.dnnList:
                    _dnn = self.state.current_config.get_dnn(dnn)
                    if _dnn is None:
                        raise ValueError(f"DNN not found for DNN: {dnn}")
                    self.state.free5gc_config_values.add_dnn_amf_item(dnn)
                    self.state.free5gc_config_values.add_dnn_info_smf_item(dnn, _dnn.dns, _slice)
                    # self.state.free5gc_config_values.add_dnnupfinfolist_smf(f"gNB{sub_area.id}", f"UPF{sub_area.id}", deployed_upf_info.network_info.n4_ip.exploded, deployed_upf_info.network_info.n3_ip.exploded, sub_slice.sliceType, sub_slice.sliceId, dnn, _dnn.pools[0].cidr)
                    self.state.free5gc_config_values.add_dnnupfinfolist_smf(f"gNB", f"UPF{sub_area.id}", deployed_upf_info.network_info.n4_ip.exploded, deployed_upf_info.network_info.n3_ip.exploded, sub_slice.sliceType, sub_slice.sliceId, dnn, _dnn.pools[0].cidr)

    def update_core(self):
        """
        Restart all the pods. (Use the "update_core_values", then call this function to restart pods with new values).

        """
        self.update_core_values()
        self.provider.update_values_helm_chart(
            self.state.core_helm_chart,
            self.state.free5gc_config_values.model_dump(exclude_none=True, by_alias=True)
        )

    def post_creation(self):
        nfs = self.network_functions_dictionary()
        smf_dep = nfs[NF5GType.SMF][0]
        self.provider.restart_deployment(self.state.core_helm_chart, self.state.core_helm_chart.deployments[smf_dep].name)

    def get_gpsi(self):
        """
        GPSI randomizer
        Returns: a random gpsi

        """
        while True:
            gpsi = f"+{''.join(random.choices(string.digits, k=random.randint(9, 15)))}"
            if gpsi not in self.state.gpsis:
                self.state.gpsis.append(gpsi)
                return gpsi

    def add_ues(self, subscriber_model: Core5GAddSubscriberModel):
        gpsi = self.get_gpsi()
        subscriber = copy.deepcopy(free5gc_subscriber_config.subscriber_config)
        subscriber.update_subscriber_config(subscriber_model.imsi, self.state.current_config, gpsi=gpsi)
        command = ["mongosh", "mongodb://mongodb/free5gc", "--eval", subscriber.to_mongosh_insert()]
        response = self.provider.spawn_pod(
            helm_chart_resource=self.state.core_helm_chart,
            pod_name=f"mongosh-add-{subscriber_model.imsi}",
            image="mongo:7",
            command=command,
            wait_for_completion=True
        )
        self.logger.info(response)
        self.state.subscribers.append(subscriber)

    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        subscriber = self.get_subscriber(subscriber_model.imsi)
        command = ["mongosh", "mongodb://mongodb/free5gc", "--eval", subscriber.to_mongosh_delete()]
        response = self.provider.spawn_pod(
            helm_chart_resource=self.state.core_helm_chart,
            pod_name=f"mongosh-del-{subscriber_model.imsi}",
            image="mongo:7",
            command=command,
            wait_for_completion=True
        )
        self.logger.info(response)
        self.state.subscribers.remove(subscriber)

    def add_slice(self, add_slice_model: Core5GAddSliceModel, oss: bool):
        super().add_slice(add_slice_model, oss=oss)
        self.update_edge_areas()

    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        super().del_slice(del_slice_model)
        self.update_edge_areas()

    def add_tac(self, add_area_model: Core5GAddTacModel):
        super().add_tac(add_area_model)
        self.update_edge_areas()

    def del_tac(self, del_area_model: Core5GDelTacModel):
        super().del_tac(del_area_model)
        self.update_edge_areas()

    def get_subscriber(self, imsi: str) -> Free5gcSubScriber:
        for _subscriber in self.state.subscribers:
            if _subscriber.ue_id == f"imsi-{imsi}":
                return _subscriber
        raise ValueError(f'Subscriber with imsi: {imsi} not found.')
