import copy
from typing import Optional, List, Dict

import httpx
from pydantic import Field
from starlette.requests import Request

from blueprints.blue_5g_base.blueprint_5g_base_beta import SstConvertion
from blueprints.blue_5g_base.models.blue_5g_model import SubArea, SubSubscribers, SubDataNets, SubSliceProfiles, SubSlices
from blueprints.blue_oai_cn5g.models import OAIBlueCreateModel
from blueprints.blue_oai_cn5g.models.blue_OAI_model import DnnItem, Snssai, OAIModelServices, OAIDelSubscriberModel, \
    OAIAddSliceModel, OAIDelSliceModel, OAIAddTacModel, OAIDelTacModel, Ue, OaiCoreValuesModel, Upfconfig, SessionManagementSubscriptionData, DnnConfiguration, SessionAmbr, FiveQosProfile
from blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState
from blueprints_ng.lcm.blueprint_route_manager import add_route
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.modules.oai import oai_default_core_config, oai_utils
from blueprints_ng.modules.ueransim.ueransim_models import UeransimBlueprintRequestConfigureGNB, UeransimSlice
from blueprints_ng.resources import HelmChartResource
from models.blueprint_ng.g5.upf import UpfPayloadModel, SliceModel, DnnModel
from models.http_models import HttpRequestType
from utils.log import create_logger

OAI_CORE_BLUE_TYPE = "OpenAirInterface"
logger = create_logger('OpenAirInterface')


class OAIBlueprintNGState(BlueprintNGState):
    """
    This class represent the current state of the blueprint, the data contained in this class will be saved to the DB

    Every Resource should be stored in a variable in this class to be able to access it after the initial creation

    Everything in this class should be serializable by Pydantic

    Every field need to be Optional because the state is created empty
    """
    oai_config_values: Optional[OaiCoreValuesModel] = Field(default=None)
    ue_dict: Dict[str, List[Snssai]] = {}
    config_model: Optional[OAIBlueCreateModel] = Field(default=None)
    mcc: Optional[str] = Field(default=None)
    mnc: Optional[str] = Field(default=None)

    oai_helm_chart: Optional[HelmChartResource] = Field(default=None)
    udr_ip: Optional[str] = Field(default=None)
    nrf_ip: Optional[str] = Field(default=None)
    amf_ip: Optional[str] = Field(default=None)


@declare_blue_type(OAI_CORE_BLUE_TYPE)
class OpenAirInterface(BlueprintNG[OAIBlueprintNGState, OAIBlueCreateModel]):

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = OAIBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: OAIBlueCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of Open Air Interface blueprint")

        core_area: SubArea = list(filter(lambda x: x.core, create_model.areas))[0]

        self.state.oai_config_values = copy.deepcopy(oai_default_core_config.default_core_config)
        self.state.config_model = create_model
        self.state.oai_helm_chart = HelmChartResource(
            area=core_area.id,
            name=f"oai",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/oai5gbasic-2.0.0.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.oai_helm_chart)

        self.state.mcc = create_model.config.plmn[0:3]
        self.state.mnc = create_model.config.plmn[-2:]

        self.state.oai_config_values.coreconfig.amf.served_guami_list.clear()
        oai_utils.add_served_guami_list_item(config=self.state.oai_config_values.coreconfig, mcc=self.state.mcc, mnc=self.state.mnc)

        self.state.oai_config_values.oai_smf.hostAliases.clear()
        self.state.oai_config_values.coreconfig.smf.upfs.clear()
        self.state.oai_config_values.coreconfig.snssais.clear()
        self.state.oai_config_values.coreconfig.amf.plmn_support_list.clear()
        self.state.oai_config_values.coreconfig.smf.smf_info.sNssaiSmfInfoList.clear()
        self.state.oai_config_values.coreconfig.smf.local_subscription_infos.clear()
        self.state.oai_config_values.coreconfig.dnns.clear()

        for sub_area in create_model.areas:
            ip_upf = self.call_external_function(sub_area.upf_bp_id, "get_ip")

            oai_utils.add_host_aliases(self.state.oai_config_values.oai_smf, sub_area.id, ip_upf)
            oai_utils.add_available_upf(self.state.oai_config_values.coreconfig, sub_area.id)

            for slice in sub_area.slices:
                new_snssai = oai_utils.add_snssai(self.state.oai_config_values.coreconfig, slice.sliceId, slice.sliceType)
                oai_utils.add_plmn_item(self.state.oai_config_values.coreconfig, self.state.mcc, self.state.mnc, sub_area.id, new_snssai)
                sub_slice = self.get_slice(slice.sliceId)
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

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.oai_helm_chart,
            self.state.oai_config_values.model_dump(exclude_none=True, by_alias=True)
        )

        self.state.udr_ip = self.state.oai_helm_chart.services["oai-udr-svc-lb"].external_ip[0]
        self.state.nrf_ip = self.state.oai_helm_chart.services["oai-nrf-svc-lb"].external_ip[0]
        self.state.amf_ip = self.state.oai_helm_chart.services["oai-amf-svc-lb"].external_ip[0]

        for sub_area in create_model.areas:
            self.update_upf_config(sub_area.id)
            self.update_gnb_config(sub_area.id)

        for subscriber in create_model.config.subscribers:
            self.add_ues(subscriber)

    def update_upf_config(self, area_id: int):
        """

        Args:
            area_id:

        Returns:

        """
        area = self.get_area(area_id)
        upf_payload = UpfPayloadModel(
            nrf_ip=self.state.nrf_ip,
            slices=[]
        )
        for slice in area.slices:

            slice_payload = SliceModel(
                id=slice.sliceId,
                type=slice.sliceType,
                dnnList=[]
            )
            # slice_payload.id = slice.sliceId
            # slice_payload.type = SstConvertion.to_int(slice.sliceType)

            sub_slice = self.get_slice(slice.sliceId)
            for dnn in sub_slice.dnnList:
                dnn_payload = DnnModel()

                dnn_info = self.get_dnn(dnn)

                dnn_payload.name = dnn_info.net_name
                dnn_payload.cidr = dnn_info.pools[0].cidr
                slice_payload.dnnList.append(dnn_payload)

            upf_payload.slices.append(slice_payload)

        self.call_external_function(area.upf_bp_id, "configure", upf_payload)

    def update_gnb_config(self, area_id: int):
        """

        Args:
            area_id:

        Returns:

        """
        area = self.get_area(area_id)
        gnb_payload = UeransimBlueprintRequestConfigureGNB(
            area=area_id,
            tac=area_id,
            plmn=self.state.config_model.config.plmn,
            amf_ip=self.state.amf_ip,
            amf_port=38412,
            nssai=[]
        )

        # gnb_payload.area = area_id
        # gnb_payload.tac = area_id
        # gnb_payload.plmn = self.state.config_model.config.plmn
        # gnb_payload.amf_ip = self.state.amf_ip
        # gnb_payload.amf_port = 38412

        for slice in area.slices:
            slice_gnb = UeransimSlice(
                sd=int(slice.sliceId),
                sst=SstConvertion.to_int(slice.sliceType)
            )
            # slice_gnb.sd = slice.sliceId
            # slice_gnb.sst = SstConvertion.to_int(slice.sliceType)
            gnb_payload.nssai.append(slice_gnb)

        self.call_external_function(area.gnb_bp_id, "configure_gnb", gnb_payload)

    def add_area_to_conf(self, area: OAIAddTacModel):
        """

        Args:
            area:

        Returns:

        """
        new_area: SubArea = SubArea.model_validate(area.model_dump(by_alias=True))
        if any(sub_area.id == new_area.id for sub_area in self.state.config_model.areas):
            return False
        slices = list(filter(lambda x: x.sliceId in new_area.slices, self.state.config_model.config.sliceProfiles))
        if len(slices) == 0:
            return False
        self.state.config_model.areas.append(new_area)
        return True

    def del_area_from_conf(self, area: OAIDelTacModel):
        """

        Args:
            area:

        Returns:

        """
        old_area: SubArea = SubArea.model_validate(area.model_dump(by_alias=True))
        if old_area in self.state.config_model.areas.copy():
            self.state.config_model.areas.remove(old_area)
            return True
        return False

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
        if any(sub_slice.sliceId == new_slice.sliceId for sub_slice in self.state.config_model.config.sliceProfiles):
            return False
        self.state.config_model.config.sliceProfiles.append(new_slice)
        if add_slice_model.area_id is not None:
            area = self.get_area(add_slice_model.area_id)
            area.slices.append(SubSlices(
                sliceType=new_slice.sliceType,
                sliceId=new_slice.sliceId
            ))
            return True
        else:
            return False

    def del_slice_from_conf(self, sub_slice: SubSliceProfiles, sub_area: SubArea = None) -> bool:
        """
        Delete a slice from "sliceProfiles" initial configuration.
        :param sub_slice: Slice to remove.
        :param sub_area: Area of the slice to remove (optional, default is None).
        :return: True if successfully removed slice from specified area, False otherwise (if area provided).
                 True if successfully removed slice, False otherwise (if area not provided).
        """
        if sub_slice and sub_area:
            for slice in sub_area.slices.copy():
                if slice.sliceId == sub_slice.sliceId:
                    self.state.config_model.config.sliceProfiles.remove(sub_slice)
                    sub_area.slices.remove(slice)
                    return True
            return False
        elif sub_slice and not sub_area:
            self.state.config_model.config.sliceProfiles.remove(sub_slice)
            return True
        return False

    def get_slice(self, slice_id: str) -> SubSliceProfiles:
        """
        Get slice from "sliceProfiles".
        :param slice_id: id of slice to retrieve.
        :return: Slice if exists, None otherwise.
        """

        for slice in self.state.config_model.config.sliceProfiles:
            if slice.sliceId == slice_id:
                return slice
        raise ValueError(f'Slice {slice_id} not found.')

    def get_area(self, area_id: int) -> SubArea:
        """
        Get area from "areas".
        :param area_id: id of area to retrieve.
        :return: Area if exists, None otherwise.
        """
        for area in self.state.config_model.areas:
            if area_id == area.id:
                return area
        raise ValueError(f'Area {area_id} not found.')

    def get_area_from_sliceid(self, sliceid: str) -> SubArea:
        """
        Get area from "areas".
        :param sliceid: id of slice that have to be in area.
        :return: Area with that slice, None otherwise.
        """

        for area in self.state.config_model.areas:
            for slice in area.slices:
                if slice.sliceId == sliceid:
                    return area
        raise ValueError(f'Area of slice {sliceid} not found.')

    def get_dnn(self, dnn_name: str) -> SubDataNets:
        """
        Get dnn from "network_endpoints" -> "data_nets".
        :param dnn_name: name of dnn to retrieve.
        :return: Dnn if exists, None otherwise.
        """
        for dnn in self.state.config_model.config.network_endpoints.data_nets:
            if dnn_name == dnn.dnn:
                return dnn
        raise ValueError(f'Dnn {dnn_name} not found.')

    @classmethod
    def rest_create(cls, msg: OAIBlueCreateModel, request: Request):
        return cls.api_day0_function(msg, request)

    @classmethod
    def rest_add_subscriber(cls, add_subscriber_model: SubSubscribers, blue_id: str, request: Request):
        return cls.api_day2_function(add_subscriber_model, blue_id, request)

    @classmethod
    def rest_del_subscriber(cls, del_subscriber_model: OAIDelSubscriberModel, blue_id: str, request: Request):
        return cls.api_day2_function(del_subscriber_model, blue_id, request)

    @classmethod
    def rest_add_slice(cls, add_slice_model: OAIAddSliceModel, blue_id: str, request: Request):
        return cls.api_day2_function(add_slice_model, blue_id, request)

    @classmethod
    def rest_del_slice(cls, del_slice_model: OAIDelSliceModel, blue_id: str, request: Request):
        return cls.api_day2_function(del_slice_model, blue_id, request)

    @classmethod
    def rest_add_tac(cls, add_tac_model: OAIAddTacModel, blue_id: str, request: Request):
        return cls.api_day2_function(add_tac_model, blue_id, request)

    @classmethod
    def rest_del_tac(cls, del_tac_model: OAIDelTacModel, blue_id: str, request: Request):
        return cls.api_day2_function(del_tac_model, blue_id, request)

    @add_route(OAI_CORE_BLUE_TYPE, "/add_subscriber", [HttpRequestType.PUT], rest_add_subscriber)
    def add_ues(self, subscriber_model: SubSubscribers) -> list:
        """
        Calls OAI api to add new UE and his SMS (Session Management Subscription) to DB.
        :param subscriber_model: UE to add.
        """
        if subscriber_model.imsi not in self.state.ue_dict.keys():
            logger.info(f"Try to add user: {subscriber_model.imsi}")
            with httpx.Client(http1=False, http2=True) as client:
                # Add UE to DB
                api_url_ue = f"http://{self.state.udr_ip}:80/nudr-dr/v1/subscription-data/{subscriber_model.imsi}/authentication-data/authentication-subscription"
                payload_ue = Ue(
                    authentication_method=subscriber_model.authenticationMethod,
                    enc_permanent_key=subscriber_model.k,
                    protection_parameter_id=subscriber_model.k,
                    enc_opc_key=subscriber_model.opc,
                    enc_topc_key=subscriber_model.opc,
                    supi=subscriber_model.imsi
                )
                response = client.put(api_url_ue, json=payload_ue.model_dump(by_alias=True))
                logger.info(f"Status code: {response.status_code}")
                logger.info(f"Response content: {response.text}")

                # Add Session Management Subscription to DB
                api_url_sms = f"http://{self.state.udr_ip}:80/nudr-dr/v1/subscription-data/{subscriber_model.imsi}/{self.state.config_model.config.plmn}/provisioned-data/sm-data"
                single_nssai = Snssai(
                    sst=SstConvertion.to_int(subscriber_model.snssai[0].sliceType),
                    sd=str(int(subscriber_model.snssai[0].sliceId, 16))
                )
                # Only 1 slice for subscriber and plmn is supported by OAI
                self.state.ue_dict[subscriber_model.imsi] = []
                self.state.ue_dict[subscriber_model.imsi].append(single_nssai)
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
                            five_qi=int(sub_dnn.default5qi)
                        )
                    )
                    payload_sms.add_configuration(dnn, configuration)
                    response = client.put(api_url_sms, json=payload_sms.model_dump(by_alias=True))
                    logger.info(f"Status code: {response.status_code}")
                    logger.info(f"Response content: {response.text}")

        return []

    @add_route(OAI_CORE_BLUE_TYPE, "/del_subscriber", [HttpRequestType.DELETE], rest_del_subscriber)
    def del_ues(self, subscriber_model: OAIDelSubscriberModel) -> list:
        """
        Calls OAI api to delete an existing UE and all his related SMS from DB.
        :param subscriber_model: imsi to delete.
        """
        if subscriber_model.imsi in self.state.ue_dict.keys():
            logger.info(f"Try to delete user: {subscriber_model.imsi}")
            with httpx.Client(http1=False, http2=True) as client:
                api_url = f"http://{self.state.udr_ip}:80/nudr-dr/v1/subscription-data/{subscriber_model.imsi}/authentication-data/authentication-subscription"
                response = client.delete(api_url)
                logger.info(f"Status code: {response.status_code}")
                logger.info(f"Response content: {response.text}")

            for sms in self.state.ue_dict[subscriber_model.imsi]:
                with httpx.Client(http1=False, http2=True) as client:
                    api_url = f"http://{self.state.udr_ip}:80/nudr-dr/v1/subscription-data/{subscriber_model.imsi}/{self.state.config_model.config.plmn}/provisioned-data/sm-data"
                    response = client.delete(api_url, params={'sst': sms.sst, 'sd': sms.sd})
                    logger.info(f"Status code: {response.status_code}")
                    logger.info(f"Response content: {response.text}")

                del self.state.ue_dict[subscriber_model.imsi]
        return []

    @add_route(OAI_CORE_BLUE_TYPE, "/add_slice", [HttpRequestType.PUT], rest_add_slice)
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
        added = self.add_slice_to_conf(add_slice_model)
        if added and add_slice_model.area_id is not None:
            # Add SNSSAI
            new_snssai = oai_utils.add_snssai(self.state.oai_config_values.coreconfig, add_slice_model.sliceId, add_slice_model.sliceType)

            # Add plmn item
            oai_utils.add_plmn_item(self.state.oai_config_values.coreconfig, self.state.mcc, self.state.mnc, add_slice_model.area_id, new_snssai)

            for dnn in add_slice_model.dnnList:
                dnn_item = DnnItem(
                    dnn=dnn
                )
                dnn_info = self.get_dnn(dnn)
                # Add dnns
                oai_utils.add_dnn_dnns(self.state.oai_config_values.coreconfig, dnn_info.dnn, dnn_info.pools[0].cidr)

                # Add snssai upf/smf info list
                oai_utils.add_dnn_snssai_smf_info_list_item(self.state.oai_config_values.coreconfig, new_snssai, dnn_item)

                # Add local subscription info
                oai_utils.add_local_subscription_info(self.state.oai_config_values.coreconfig, new_snssai, dnn_info)

            # In the chart installation a dict containing the values overrides can be passed
            self.provider.update_values_helm_chart(
                self.state.oai_helm_chart,
                self.state.oai_config_values.model_dump(exclude_none=True, by_alias=True)
            )

            self.update_upf_config(add_slice_model.area_id)
            self.update_gnb_config(add_slice_model.area_id)

        return res

    @add_route(OAI_CORE_BLUE_TYPE, "/del_slice", [HttpRequestType.DELETE], rest_del_slice)
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

        # Delete SNSSAI
        snssai = oai_utils.del_snssai(self.state.oai_config_values.coreconfig, del_slice_model.sliceId)

        # Delete plmn item
        oai_utils.del_plmn_item(self.state.oai_config_values.coreconfig, self.state.mcc, self.state.mnc, sub_area.id, snssai)

        for dnn in sub_slice.dnnList:
            # Add local subscription info
            oai_utils.del_local_subscription_info(self.state.oai_config_values.coreconfig, del_slice_model.sliceId, dnn)

        # Delete snssai upf/smf info list
        oai_utils.destroy_snssai_smf_info_list_item(self.state.oai_config_values.coreconfig, del_slice_model.sliceId)

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.update_values_helm_chart(
            self.state.oai_helm_chart,
            self.state.oai_config_values.model_dump(exclude_none=True, by_alias=True)
        )

        self.update_upf_config(sub_area.id)
        self.update_gnb_config(sub_area.id)

        # Update UE DB
        for imsi in self.state.ue_dict.keys():
            for ue_slice in self.state.ue_dict[imsi].copy():
                if del_slice_model.sliceId == ue_slice.sd:
                    self.state.ue_dict[imsi].remove(ue_slice)
                    # if len(self.state.ue_dict[imsi]) == 0:
                    #     self.del_ues(del_slice_model.imsi)

        self.del_slice_from_conf(sub_slice, sub_area)
        return res

    @add_route(OAI_CORE_BLUE_TYPE, "/add_tac", [HttpRequestType.PUT], rest_add_tac)
    def add_tac(self, area: OAIAddTacModel):
        """
        Create the new VM where UPF will run.
        :param area: new area to add.
        :return: day2 instruction to create new VM.
        """
        added = self.add_area_to_conf(area)
        if added:
            ip_upf = self.call_external_function(area.upf_bp_id, "get_ip")

            oai_utils.add_host_aliases(self.state.oai_config_values.oai_smf, area.id, ip_upf)
            oai_utils.add_available_upf(self.state.oai_config_values.coreconfig, area.id)

            for slice in area.slices:
                new_snssai = oai_utils.add_snssai(self.state.oai_config_values.coreconfig, slice.sliceId, slice.sliceType)
                oai_utils.add_plmn_item(self.state.oai_config_values.coreconfig, self.state.mcc, self.state.mnc, area.id, new_snssai)
                sub_slice = self.get_slice(slice.sliceId)
                for dnn in sub_slice.dnnList:
                    dnn_item = DnnItem(
                        dnn=dnn
                    )
                    dnn_info = self.get_dnn(dnn)
                    oai_utils.add_local_subscription_info(self.state.oai_config_values.coreconfig, new_snssai, dnn_info)
                    oai_utils.add_dnn_dnns(self.state.oai_config_values.coreconfig, dnn_info.dnn, dnn_info.pools[0].cidr)
                    oai_utils.add_dnn_snssai_smf_info_list_item(self.state.oai_config_values.coreconfig, new_snssai, dnn_item)

            # In the chart installation a dict containing the values overrides can be passed
            self.provider.update_values_helm_chart(
                self.state.oai_helm_chart,
                self.state.oai_config_values.model_dump(exclude_none=True, by_alias=True)
            )

            self.update_upf_config(area.id)
            self.update_gnb_config(area.id)

    @add_route(OAI_CORE_BLUE_TYPE, "/del_tac", [HttpRequestType.DELETE], rest_del_tac)
    def del_tac(self, area: OAIDelTacModel):
        """
        Delete area from configuration and update the core.
        :param area: area to delete.
        :return: day2 instruction to delete area and update core.
        """
        deleted = self.del_area_from_conf(area)
        if deleted:
            oai_utils.del_host_aliases(self.state.oai_config_values.oai_smf, area.id)
            oai_utils.del_available_upf(self.state.oai_config_values.coreconfig, area.id)

            for slice in area.slices:
                del_snssai = oai_utils.del_snssai(self.state.oai_config_values.coreconfig, slice.sliceId)
                oai_utils.destroy_plmn_list(self.state.oai_config_values.coreconfig, self.state.mcc, self.state.mnc, area.id)
                sub_slice = self.get_slice(slice.sliceId)
                for dnn in sub_slice.dnnList:
                    oai_utils.del_local_subscription_info(self.state.oai_config_values.coreconfig, del_snssai.sd, dnn)
                    oai_utils.destroy_snssai_smf_info_list_item(self.state.oai_config_values.coreconfig, del_snssai.sd)

            # In the chart installation a dict containing the values overrides can be passed
            self.provider.update_values_helm_chart(
                self.state.oai_helm_chart,
                self.state.oai_config_values.model_dump(exclude_none=True, by_alias=True)
            )
