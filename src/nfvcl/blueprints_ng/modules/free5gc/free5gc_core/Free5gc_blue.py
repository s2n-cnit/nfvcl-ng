import copy
import random
import string
from typing import Optional, Dict, List, Tuple

import httpx
from pydantic import Field

from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.free5gc import free5gc_default_core_config, free5gc_subscriber_config
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_k8s import Generic5GK8sBlueprintNGState, Generic5GK8sBlueprintNG
from nfvcl.blueprints_ng.resources import HelmChartResource
from nfvcl.models.blueprint_ng.core5g.common import Create5gModel, SubArea, SubSliceProfiles, SubSubscribers, SubDataNets, SstConvertion
from nfvcl.models.blueprint_ng.free5gc.free5gcCore import Free5gcCoreConfig, Snssai, Free5gcLogin, Free5gcSubScriber
from nfvcl.models.blueprint_ng.g5.core import Core5GDelTacModel, Core5GAddTacModel, Core5GDelSliceModel, Core5GAddSliceModel, Core5GDelSubscriberModel, Core5GAddSubscriberModel, NF5GType, Core5GAddDnnModel, Core5GDelDnnModel
from nfvcl.utils.log import create_logger

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


@blueprint_type(FREE5GC_CORE_BLUE_TYPE)
class Free5gc(Generic5GK8sBlueprintNG[Free5gcBlueprintNGState, Free5gcBlueCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GK8sBlueprintNGState] = Free5gcBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB.

        """
        super().__init__(blueprint_id, state_type)

    def network_functions_dictionary(self) -> Dict[NF5GType, Tuple[str, str]]:
        return {
            NF5GType.AMF: ("amf", "free5gc-free5gc-amf-amf-n2"),
            NF5GType.AUSF: ("ausf", "free5gc-free5gc-ausf-service"),
            NF5GType.NRF: ("nrf", "nrf-nnrf"),
            NF5GType.SMF: ("smf", "free5gc-free5gc-smf-service"),
            NF5GType.UDM: ("udm", "free5gc-free5gc-udm-service"),
            NF5GType.UDR: ("udr", "free5gc-free5gc-udr-service"),
            NF5GType.NSSF: ("nssf", "free5gc-free5gc-nssf-service"),
            NF5GType.PCF: ("pcf", "free5gc-free5gc-pcf-service"),
            NF5GType.WEBUI: ("webui", "webui-service")
        }

    def create_5g(self, create_model: Create5gModel):
        self.logger.info("Starting creation of Free5gc blueprint")

        core_area: SubArea = list(filter(lambda x: x.core, create_model.areas))[0]

        self.state.free5gc_config_values = copy.deepcopy(free5gc_default_core_config.default_core_config)

        self.state.core_helm_chart = HelmChartResource(
            area=core_area.id,
            name="free5gc",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/free5gc-3.4.2.tgz",
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
        self.state.smf_ip = self.state.k8s_network_functions[NF5GType.SMF].service.external_ip[0]
        self.state.webui_ip = self.state.k8s_network_functions[NF5GType.WEBUI].service.external_ip[0]

        self.state.base_webui_api = f"http://{self.state.webui_ip}:5000/api"

        self.update_core_values()
        self.update_core()

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
        if self.state.smf_ip:
            self.state.free5gc_config_values.set_smf_ip(self.state.smf_ip)

        self.state.free5gc_config_values.set_default_nrf_plmnd(self.state.mcc, self.state.mnc)
        self.state.free5gc_config_values.add_item_amf_servedGuamiList(self.state.mcc, self.state.mnc)
        self.state.free5gc_config_values.add_plmn_smf_item(self.state.mcc, self.state.mnc)
        self.state.free5gc_config_values.add_plmn_ausf_item(self.state.mcc, self.state.mnc)
        self.state.free5gc_config_values.add_supported_plmn_nssf(self.state.mcc, self.state.mnc)

        for sub_area in self.state.current_config.areas:
            deployed_upf_info = self.state.edge_areas[str(sub_area.id)].upf.upf_list[0]
            self.state.free5gc_config_values.add_item_amf_supportTaiList(self.state.mcc, self.state.mnc, str(sub_area.id).zfill(6))

            for sub_slice in sub_area.slices:
                _slice = Snssai(
                    sst=SstConvertion.to_int(sub_slice.sliceType),
                    sd=sub_slice.sliceId
                )
                self.state.free5gc_config_values.add_plmn_amf_item(self.state.mcc, self.state.mnc, sub_area.id, _slice)
                self.state.free5gc_config_values.add_supportedsnssailist_item_nssf(self.state.mcc, self.state.mnc, _slice)
                self.state.free5gc_config_values.add_nsi_list_item_nssf(SstConvertion.to_int(sub_slice.sliceType), sub_slice.sliceId, self.state.nsi_nssf_id)
                self.state.nsi_nssf_id = self.state.nsi_nssf_id + 1
                self.state.free5gc_config_values.add_supported_nssai_nssf(self.state.supported_nssai_availability_nssf_id, self.state.mcc, self.state.mnc, str(sub_area.id).zfill(6), _slice)
                self.state.supported_nssai_availability_nssf_id = self.state.supported_nssai_availability_nssf_id + 1
                self.state.free5gc_config_values.add_tai_supportedsnssailist_nssf_item(self.state.mcc, self.state.mnc, str(sub_area.id).zfill(6), _slice)

                for dnn in self.get_slice(_slice.sd).dnnList:
                    _dnn = self.get_dnn(dnn)
                    self.state.free5gc_config_values.add_dnn_amf_item(dnn)
                    self.state.free5gc_config_values.add_dnn_info_smf_item(dnn, _dnn.dns, _slice)
                    self.state.free5gc_config_values.add_dnnupfinfolist_smf(f"gNB{sub_area.id}", f"UPF{sub_area.id}", deployed_upf_info.network_info.n4_ip.exploded, deployed_upf_info.network_info.n3_ip.exploded, SstConvertion.to_int(sub_slice.sliceType), sub_slice.sliceId, dnn, _dnn.pools[0].cidr)


    def update_core(self):
        """
        Restart all the pods. (Use the "update_core_values", then call this function to restart pods with new values).

        """
        self.provider.update_values_helm_chart(
            self.state.core_helm_chart,
            self.state.free5gc_config_values.model_dump(exclude_none=True, by_alias=True)
        )

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

    def get_api_token(self):
        """
        Get API access token
        Returns: API access token

        """
        self.logger.info("Requesting API access token")
        with httpx.Client(http1=True, http2=False, base_url=self.state.base_webui_api) as client:
            api_url_ue = f"/login"
            response = client.post(api_url_ue, json=free5gc_credentials)
            token = Free5gcLogin.model_validate(response.json())
            logger.info(f"Status code: {response.status_code}")
            return token.access_token

    def add_ues(self, subscriber_model: Core5GAddSubscriberModel):
        api_token = self.get_api_token()
        gpsi = self.get_gpsi()
        subscriber = copy.deepcopy(free5gc_subscriber_config.subscriber_config)
        subscriber.update_subscriber_config(subscriber_model.imsi, self.state.current_config, gpsi=gpsi)

        with httpx.Client(http1=True, http2=False, base_url=self.state.base_webui_api) as client:
            api_url_ue = f"/subscriber/{subscriber.ue_id}/{subscriber.plmn_id}"
            response = client.post(api_url_ue, headers={'token': f'{api_token}'}, json=subscriber.model_dump(by_alias=True))
            logger.info(f"Status code: {response.status_code}")

    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        api_token = self.get_api_token()
        with httpx.Client(http1=True, http2=False, base_url=self.state.base_webui_api) as client:
            api_url_ue = f"/subscriber/imsi-{subscriber_model.imsi}/{subscriber_model.imsi[:5]}"
            response = client.delete(api_url_ue, headers={'token': f'{api_token}'})
            logger.info(f"Status code: {response.status_code}")

    def add_slice(self, add_slice_model: Core5GAddSliceModel, oss: bool):
        self.update_edge_areas()
        self.update_core_values()
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_config()

    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        api_token = self.get_api_token()
        with httpx.Client(http1=True, http2=False, base_url=self.state.base_webui_api) as client:
            for subscriber in self.state.current_config.config.subscribers:
                for _slice in subscriber.snssai:
                    if _slice.sliceId == del_slice_model.sliceId:
                        api_url_ue = f"/subscriber/imsi-{subscriber.imsi}/{subscriber.imsi[:5]}"

                        response = client.get(api_url_ue, headers={'token': f'{api_token}'})
                        logger.info(f"Status code: {response.status_code}")

                        user = Free5gcSubScriber.model_validate(response.json())
                        user.update_subscriber_config(subscriber.imsi, self.state.current_config)
                        response = client.put(api_url_ue, headers={'token': f'{api_token}'}, json=user.model_dump(by_alias=True))
                        logger.info(f"Status code: {response.status_code}")

        self.update_edge_areas()
        self.update_core_values()
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_config()

    def add_tac(self, add_area_model: Core5GAddTacModel):
        self.update_edge_areas()
        self.update_core_values()
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_config()

    def del_tac(self, del_area_model: Core5GDelTacModel):
        self.update_edge_areas()
        self.update_core_values()
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_config()

    def add_dnn(self, dnn_model: Core5GAddDnnModel):
        pass

    def del_dnn(self, del_dnn_model: Core5GDelDnnModel):
        pass

    def get_slice(self, slice_id: str) -> SubSliceProfiles:
        """
        Get SubSliceProfiles with specified slice_id from conf.
        Args:
            slice_id: slice id of the slice to retrieve.

        Returns: the slice with specified slice_id.

        """
        for _slice in self.state.current_config.config.sliceProfiles:
            if _slice.sliceId == slice_id:
                return _slice
        raise ValueError(f'Slice {slice_id} not found.')

    def get_subscriber(self, imsi: str) -> SubSubscribers:
        """
        Get SubSubscribers with specified imsi from conf.
        Args:
            imsi: imsi of the subscriber to retrieve.

        Returns: the subscriber with specified imsi.

        """
        for _subscriber in self.state.current_config.config.subscribers:
            if _subscriber.imsi == imsi:
                return _subscriber
        raise ValueError(f'Subscriber with imsi: {imsi} not found.')

    def get_area(self, area_id: int) -> SubArea:
        """
        Get SubArea with specified area_id from conf.
        Args:
            area_id: area id of the area to retrieve.

        Returns: the area with specified area id.

        """
        for area in self.state.current_config.areas:
            if area_id == area.id:
                return area
        raise ValueError(f'Area {area_id} not found.')

    def get_area_from_sliceid(self, sliceid: str) -> SubArea:
        """
        Get SubArea from conf, that contains the slice with specified sliceid.
        Args:
            sliceid: slice id of the slice.

        Returns: the area with specified slice.

        """
        for area in self.state.current_config.areas:
            for slice in area.slices:
                if slice.sliceId == sliceid:
                    return area
        raise ValueError(f'Area of slice {sliceid} not found.')

    def get_dnn(self, dnn_name: str) -> SubDataNets:
        """
        Get SubDataNets with specified dnn_name from conf.
        Args:
            dnn_name: dnn name of the dnn to retrieve.

        Returns: the dnn with specified dnn name.

        """
        for dnn in self.state.current_config.config.network_endpoints.data_nets:
            if dnn_name == dnn.dnn:
                return dnn
        raise ValueError(f'Dnn {dnn_name} not found.')
