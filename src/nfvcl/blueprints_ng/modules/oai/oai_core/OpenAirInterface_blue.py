from __future__ import annotations

import copy
from typing import Optional, List, Dict, Tuple

import httpx
from pydantic import Field

from nfvcl_core.blueprints.blueprint_ng import BlueprintNGException
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_k8s import Generic5GK8sBlueprintNG, Generic5GK8sBlueprintNGState
from nfvcl.blueprints_ng.modules.oai import oai_default_core_config, oai_utils
from nfvcl.blueprints_ng.modules.oai.oai_upf.OpenAirInterfaceUpf_blue import OAI_UPF_BLUE_TYPE
from nfvcl_core.models.resources import HelmChartResource
from nfvcl.models.blueprint_ng.core5g.OAI_Models import DnnItem, Snssai, Ue, \
    SessionManagementSubscriptionData, DnnConfiguration, SessionAmbr, FiveQosProfile, OaiCoreValuesModel
from nfvcl.models.blueprint_ng.core5g.common import SstConvertion, SubArea, SubSubscribers, SubDataNets, \
    SubSliceProfiles, Create5gModel, NetworkEndPointType
from nfvcl.models.blueprint_ng.g5.core import Core5GDelSubscriberModel, Core5GAddSliceModel, \
    Core5GDelSliceModel, Core5GAddTacModel, Core5GDelTacModel, Core5GAddDnnModel, Core5GDelDnnModel, \
    Core5GUpdateSliceModel, NF5GType, Core5GAddSubscriberModel
from nfvcl.models.blueprint_ng.g5.upf import DnnModel
from nfvcl_core.utils.log import create_logger

OAI_CORE_BLUE_TYPE = "oai"
logger = create_logger('OpenAirInterface')


class OAIBlueCreateModel(Create5gModel):
    pass


class OAIBlueprintNGState(Generic5GK8sBlueprintNGState):
    """
    This class represent the current state of the blueprint, the data contained in this class will be saved to the DB.

    Every Resource should be stored in a variable in this class to be able to access it after the initial creation.

    Everything in this class should be serializable by Pydantic.

    Every field need to be Optional because the state is created empty.

    """
    oai_config_values: Optional[OaiCoreValuesModel] = Field(default=None)
    ue_dict: Dict[str, List[Snssai]] = Field(default_factory=dict)
    mcc: Optional[str] = Field(default=None)
    mnc: Optional[str] = Field(default=None)

    udr_ip: Optional[str] = Field(default=None)
    nrf_ip: Optional[str] = Field(default=None)
    amf_ip: Optional[str] = Field(default=None)
    base_udr_url: Optional[str] = Field(default=None)


@blueprint_type(OAI_CORE_BLUE_TYPE)
class OpenAirInterface(Generic5GK8sBlueprintNG[OAIBlueprintNGState, OAIBlueCreateModel]):
    default_upf_implementation = OAI_UPF_BLUE_TYPE

    def __init__(self, blueprint_id: str, state_type: type[Generic5GK8sBlueprintNGState] = OAIBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB.

        """
        super().__init__(blueprint_id, state_type)

    def network_functions_dictionary(self) -> Dict[NF5GType, Tuple[str, str]]:
        return {
            NF5GType.AMF: ("oai-amf", "oai-amf-svc-lb"),
            NF5GType.NRF: ("oai-nrf", "oai-nrf-svc-lb"),
            NF5GType.SMF: ("oai-smf", "oai-smf-svc-lb"),
            NF5GType.UDR: ("oai-udr", "oai-udr-svc-lb")
        }

    def create_5g(self, create_model: Create5gModel):
        self.logger.info("Starting creation of Open Air Interface blueprint")

        core_area: SubArea = list(filter(lambda x: x.core, create_model.areas))[0]

        self.state.oai_config_values = copy.deepcopy(oai_default_core_config.default_core_config)

        # self.state.current_config = create_model
        self.state.core_helm_chart = HelmChartResource(
            area=core_area.id,
            name="oai",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/oai5gbasic-2.1.0.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.core_helm_chart)

        self.state.mcc = create_model.config.plmn[0:3]
        self.state.mnc = create_model.config.plmn[-2:]

        self.update_core_values()

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.core_helm_chart,
            self.state.oai_config_values.model_dump(exclude_none=True, by_alias=True)
        )
        self.update_k8s_network_functions()
        self.state.udr_ip = self.state.k8s_network_functions[NF5GType.UDR].service.external_ip[0]
        self.state.nrf_ip = self.state.k8s_network_functions[NF5GType.NRF].service.external_ip[0]
        self.state.amf_ip = self.state.k8s_network_functions[NF5GType.AMF].service.external_ip[0]

        self.state.base_udr_url = f"http://{self.state.udr_ip}:80/nudr-dr/v1/subscription-data"

        for subscriber in create_model.config.subscribers.copy():
            self.add_ues(subscriber)

    def update_core_values(self):
        """
        Update core values.

        """
        self.state.oai_config_values.mysql.persistence.enabled = self.state.current_config.config.persistence.enabled
        self.state.oai_config_values.mysql.persistence.storageClass = self.state.current_config.config.persistence.storageClass

        self.state.oai_config_values.coreconfig.amf.served_guami_list.clear()
        oai_utils.add_served_guami_list_item(config=self.state.oai_config_values.coreconfig, mcc=self.state.mcc, mnc=self.state.mnc)
        self.state.oai_config_values.coreconfig.lmf.num_gnb = len(self.state.current_config.areas)

        if self.state.network_endpoints.n2 and self.state.network_endpoints.n2.type == NetworkEndPointType.MULTUS:
            self.state.oai_config_values.oai_amf.multus.n2Interface.set_multus(True, self.state.network_endpoints.n2.multus)
            self.state.oai_config_values.coreconfig.nfs.amf.n2.interface_name = "n2" if self.state.network_endpoints.n2.multus else "eth0"
        if self.state.network_endpoints.n4 and self.state.network_endpoints.n4.type == NetworkEndPointType.MULTUS:
            self.state.oai_config_values.oai_smf.multus.n4Interface.set_multus(True, self.state.network_endpoints.n4.multus)
            self.state.oai_config_values.coreconfig.nfs.smf.n4.interface_name = "n4" if self.state.network_endpoints.n4.multus else "eth0"

        # self.state.oai_config_values.oai_smf.hostAliases.clear()
        self.state.oai_config_values.coreconfig.smf.upfs.clear()
        self.state.oai_config_values.coreconfig.snssais.clear()
        self.state.oai_config_values.coreconfig.amf.plmn_support_list.clear()
        self.state.oai_config_values.coreconfig.smf.smf_info.sNssaiSmfInfoList.clear()
        self.state.oai_config_values.coreconfig.smf.local_subscription_infos.clear()
        self.state.oai_config_values.coreconfig.dnns.clear()

        for sub_area in self.state.current_config.areas:
            # TODO this work only for oai UPF, with the sdcore one multiple UPFs may be deployed for a single area
            # deployed_upf_info = self.state.edge_areas[str(sub_area.id)].upf.upf_list[0]
            # oai_utils.add_host_aliases(self.state.oai_config_values.oai_smf, sub_area.id, deployed_upf_info.network_info.n4_ip.exploded)
            oai_utils.add_available_upf(self.state.oai_config_values.coreconfig, sub_area.id)

            for _slice in sub_area.slices:
                new_snssai = oai_utils.add_snssai(self.state.oai_config_values.coreconfig, _slice.sliceId, _slice.sliceType)
                oai_utils.add_plmn_item(self.state.oai_config_values.coreconfig, self.state.mcc, self.state.mnc, sub_area.id, new_snssai)
                sub_slice = self.get_slice(_slice.sliceId)
                for dnn in sub_slice.dnnList:
                    dnn_payload = DnnModel()

                    dnn_item = DnnItem(
                        dnn=dnn
                    )
                    dnn_info = self.get_dnn(dnn)

                    dnn_payload.name = dnn_info.net_name
                    dnn_payload.cidr = dnn_info.pools[0].cidr

                    oai_utils.add_local_subscription_info(self.state.oai_config_values.coreconfig, new_snssai, dnn_info)
                    oai_utils.add_dnn_dnns(self.state.oai_config_values.coreconfig, dnn_info.dnn, dnn_info.pools[0].cidr)
                    oai_utils.add_dnn_snssai_smf_info_list_item(self.state.oai_config_values.coreconfig, new_snssai, dnn_item)

    def update_core(self):
        """
        Restart all the pods. (Use the "update_core_values", then call this function to restart pods with new values).

        """
        self.provider.update_values_helm_chart(
            self.state.core_helm_chart,
            self.state.oai_config_values.model_dump(exclude_none=True, by_alias=True)
        )

    def wait_core_ready(self):
        pass

    def add_subscriber_to_conf(self, new_subscriber: SubSubscribers):
        """
        Add new SubSubscribers obj to conf.
        Args:
            new_subscriber: new SubSubscribers to add.

        """

        with httpx.Client(http1=False, http2=True, base_url=self.state.base_udr_url) as client:
            # Add UE to DB
            api_url_ue = f"/{new_subscriber.imsi}/authentication-data/authentication-subscription"
            payload_ue = Ue(
                authentication_method=new_subscriber.authenticationMethod,
                enc_permanent_key=new_subscriber.k,
                protection_parameter_id=new_subscriber.k,
                enc_opc_key=new_subscriber.opc,
                enc_topc_key=new_subscriber.opc,
                supi=new_subscriber.imsi
            )
            response = client.put(api_url_ue, json=payload_ue.model_dump(by_alias=True))
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Response content: {response.text}")

    def del_subscriber_to_conf(self, imsi: str):
        """
        Delete SubSubscribers with specified imsi from conf.
        Args:
            imsi: the imsi of the subscriber to delete.

        """
        # self.logger.info(f"Deleting subscriber with imsi: {imsi}")
        # subscriber = self.get_subscriber(imsi)
        with httpx.Client(http1=False, http2=True, base_url=self.state.base_udr_url) as client:
            api_url = f"/{imsi}/authentication-data/authentication-subscription"
            response = client.delete(api_url)
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Response content: {response.text}")

            if response.status_code != 204:
                raise BlueprintNGException(f"Subscriber with imsi: {imsi} not deleted")

    def associating_subscriber_with_slice(self, imsi: str):
        """
        Associate subscriber and slice.
        Args:
            imsi: imsi of subscriber to associate with slice.

        """
        logger.info(f"Associating to slice, user with imsi: {imsi}")
        if imsi in self.state.ue_dict.keys():
            raise BlueprintNGException(f"Subscriber with imsi: {imsi} already associated to a slice")

        subscriber = self.get_subscriber(imsi)
        sub_slice = self.get_slice(subscriber.snssai[0].sliceId)
        with httpx.Client(http1=False, http2=True, base_url=self.state.base_udr_url) as client:
            # Add Session Management Subscription to DB
            api_url_sms = f"/{imsi}/{self.state.current_config.config.plmn}/provisioned-data/sm-data"
            single_nssai = Snssai(
                sst=SstConvertion.to_int(subscriber.snssai[0].sliceType),
                sd=str(int(subscriber.snssai[0].sliceId, 16))
            )
            # Only 1 slice for subscriber and plmn is supported by OAI
            self.state.ue_dict[imsi] = []
            self.state.ue_dict[imsi].append(single_nssai)
            payload_sms = SessionManagementSubscriptionData(
                single_nssai=single_nssai
            )
            for dnn in sub_slice.dnnList:
                sub_dnn = self.get_dnn(dnn)
                configuration = DnnConfiguration(
                    s_ambr=SessionAmbr(
                        uplink=sub_dnn.uplinkAmbr.replace(" ", ""),
                        downlink=sub_dnn.downlinkAmbr.replace(" ", "")
                    ),
                    five_qosProfile=FiveQosProfile(
                        five_qi=int(sub_dnn.default5qi)
                    )
                )
                payload_sms.add_configuration(dnn, configuration)
                response = client.put(api_url_sms, json=payload_sms.model_dump(by_alias=True))
                logger.info(f"Status code: {response.status_code}")
                logger.info(f"Response content: {response.text}")

    def disassociating_subscriber_from_slice(self, imsi: str):
        """
        Dissociate subscriber with specified slice.
        Args:
            imsi: imsi of the subscriber to dissociate.

        """
        for sms in self.state.ue_dict[imsi]:
            # if sms.sd == sd:
            with httpx.Client(http1=False, http2=True, base_url=self.state.base_udr_url) as client:
                api_url = f"/{imsi}/{self.state.current_config.config.plmn}/provisioned-data/sm-data"
                response = client.delete(api_url, params={'sst': sms.sst, 'sd': sms.sd})
                logger.info(f"Status code: {response.status_code}")
                logger.info(f"Response content: {response.text}")

            if response.status_code == 204:
                self.state.ue_dict[imsi].remove(sms)
                if len(self.state.ue_dict[imsi]) == 0:
                    del self.state.ue_dict[imsi]

        self.update_core_values()
        self.update_core()
        self.update_gnb_config()

    def update_slice(self, update_slice_model: Core5GUpdateSliceModel):
        """
        Update an existing SubSliceProfiles of the conf.
        Args:
            update_slice_model: SubSliceProfiles to update.

        """
        self.logger.info(f"Updating Slice with ID: {update_slice_model.sliceId}")
        old_slice = self.get_slice(update_slice_model.sliceId)

        for dnn in update_slice_model.dnnList:
            self.get_dnn(dnn)

        _subscribers: List[SubSubscribers] = []

        for subscriber in self.state.current_config.config.subscribers:
            for _slice in self.state.ue_dict[subscriber.imsi].copy():
                if hex(int(_slice.sd))[2:].zfill(6) == update_slice_model.sliceId:
                    _subscribers.append(subscriber)

        self.state.current_config.config.sliceProfiles.remove(old_slice)
        self.state.current_config.config.sliceProfiles.append(update_slice_model)

        for subscriber in _subscribers:
            self.disassociating_subscriber_from_slice(subscriber.imsi)
            self.associating_subscriber_with_slice(subscriber.imsi)

        self.update_core_values()
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_config()

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

    def add_ues(self, subscriber_model: Core5GAddSubscriberModel):
        """
        Calls OAI api to add new UE and his SMS (Session Management Subscription) to DB.
        Args:
            subscriber_model: SubSubscribers to add.

        """
        self.add_subscriber_to_conf(subscriber_model)
        self.associating_subscriber_with_slice(subscriber_model.imsi)

    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        """
        Calls OAI api to delete an existing UE and all his related SMS from DB.
        Args:
            subscriber_model: SubSubscribers to remove.

        """
        # for _slice in self.state.ue_dict[subscriber_model.imsi]:
        self.disassociating_subscriber_from_slice(subscriber_model.imsi)
        self.del_subscriber_to_conf(subscriber_model.imsi)

    def add_slice(self, add_slice_model: Core5GAddSliceModel, oss: bool):
        self.update_edge_areas()
        self.update_core_values()
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_config()

    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        """
        Delete SubSliceProfiles from conf.
        Args:
            del_slice_model: SubSliceProfiles to delete.

        """
        for imsi in self.state.ue_dict.keys():
            for ue_slice in self.state.ue_dict[imsi].copy():
                if del_slice_model.sliceId == ue_slice.sd:
                    self.disassociating_subscriber_from_slice(imsi)

        self.update_edge_areas()
        self.update_core_values()
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_config()

    def add_tac(self, area: Core5GAddTacModel):
        """
        Add new SubArea to conf.
        Args:
            area: SubArea to add.

        """

        self.update_edge_areas()
        self.update_core_values()
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_config()

    def del_tac(self, area: Core5GDelTacModel):
        """
        Delete SubArea from conf.
        Args:
            area: SubArea to delete.

        """

        self.update_edge_areas()
        self.update_core_values()
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_config()

    def add_dnn(self, dnn: Core5GAddDnnModel):

        self.update_core_values()
        self.update_core()


    def del_dnn(self, dnn: Core5GDelDnnModel):

        self.update_core_values()
        self.update_core()

