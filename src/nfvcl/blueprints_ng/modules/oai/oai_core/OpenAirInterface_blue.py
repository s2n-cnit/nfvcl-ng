from __future__ import annotations

import copy
from typing import Optional, List, Dict

import httpx
from pydantic import Field

from nfvcl.models.blueprint_ng.core5g.common import SstConvertion, SubArea, SubSubscribers, SubDataNets, SubSliceProfiles, SubSlices, Create5gModel
from nfvcl.models.blueprint_ng.core5g.OAI_Models import DnnItem, Snssai, Ue, OaiCoreValuesModel, SessionManagementSubscriptionData, DnnConfiguration, SessionAmbr, FiveQosProfile
from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState, BlueprintNGException
from nfvcl.blueprints_ng.lcm.blueprint_manager import get_blueprint_manager
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type, day2_function
from nfvcl.blueprints_ng.modules.oai import oai_default_core_config, oai_utils
from nfvcl.blueprints_ng.pdu_configurators.ueransim_pdu_configurator import UERANSIMPDUConfigurator
from nfvcl.blueprints_ng.resources import HelmChartResource
from nfvcl.blueprints_ng.utils import get_class_from_path
from nfvcl.models.blueprint_ng.g5.core import Core5GDelSubscriberModel, Core5GAddSliceModel, \
    Core5GDelSliceModel, Core5GAddTacModel, Core5GDelTacModel, Core5GAddDnnModel, Core5GDelDnnModel, \
    Core5GUpdateSliceModel
from nfvcl.models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestConfigureGNB, UeransimSlice
from nfvcl.models.blueprint_ng.g5.upf import UpfPayloadModel, SliceModel, DnnModel, UPFBlueCreateModel, \
    BlueCreateModelNetworks
from nfvcl.models.http_models import HttpRequestType
from nfvcl.models.network import PduModel
from nfvcl.topology.topology import build_topology
from nfvcl.utils.log import create_logger

OAI_CORE_BLUE_TYPE = "OpenAirInterface"
logger = create_logger('OpenAirInterface')


class OAIBlueCreateModel(Create5gModel):
    type: str = OAI_CORE_BLUE_TYPE


class OAIBlueprintNGState(BlueprintNGState):
    """
    This class represent the current state of the blueprint, the data contained in this class will be saved to the DB.

    Every Resource should be stored in a variable in this class to be able to access it after the initial creation.

    Everything in this class should be serializable by Pydantic.

    Every field need to be Optional because the state is created empty.

    """
    oai_config_values: Optional[OaiCoreValuesModel] = Field(default=None)
    ue_dict: Dict[str, List[Snssai]] = {}
    upf_dict: Dict[str, str] = {}
    config_model: Optional[OAIBlueCreateModel] = Field(default=None)
    mcc: Optional[str] = Field(default=None)
    mnc: Optional[str] = Field(default=None)

    oai_helm_chart: Optional[HelmChartResource] = Field(default=None)
    udr_ip: Optional[str] = Field(default=None)
    nrf_ip: Optional[str] = Field(default=None)
    amf_ip: Optional[str] = Field(default=None)
    base_udr_url: Optional[str] = Field(default=None)


@blueprint_type(OAI_CORE_BLUE_TYPE)
class OpenAirInterface(BlueprintNG[OAIBlueprintNGState, OAIBlueCreateModel]):

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = OAIBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB.

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

        self.update_upfs_deployments()
        self.update_core_values()

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.oai_helm_chart,
            self.state.oai_config_values.model_dump(exclude_none=True, by_alias=True)
        )

        self.state.udr_ip = self.state.oai_helm_chart.services["oai-udr-svc-lb"].external_ip[0]
        self.state.nrf_ip = self.state.oai_helm_chart.services["oai-nrf-svc-lb"].external_ip[0]
        self.state.amf_ip = self.state.oai_helm_chart.services["oai-amf-svc-lb"].external_ip[0]

        self.state.base_udr_url = f"http://{self.state.udr_ip}:80/nudr-dr/v1/subscription-data"

        self.update_upfs_config()
        self.update_gnbs_config()

        for subscriber in create_model.config.subscribers.copy():
            self.add_ues(subscriber, True)

    def get_gnb_pdus(self) -> List[PduModel]:
        """
        Get all available pdus.

        Returns: List of pdus.

        """
        pdus = build_topology().get_pdus()
        ueransim_pdus = list(filter(lambda x: x.type == "UERANSIM", pdus))

        areas = list(map(lambda x: x.id, self.state.config_model.areas))

        pdus_to_return = []

        for area in areas:
            found_pdus = list(filter(lambda x: x.area == area, ueransim_pdus))
            if len(found_pdus) == 0:
                raise BlueprintNGException(f"No GNB PDU found for area '{area}'")
            if len(found_pdus) > 1:
                raise BlueprintNGException(f"More than 1 GNB PDU found for area '{area}'")
            pdus_to_return.append(found_pdus[0])

        return pdus_to_return

    def update_upfs_deployments(self):
        """
        Check for every area, if some UPF need to be created or delete.

        """
        area_ids = list(map(lambda x: str(x.id), self.state.config_model.areas))
        temp = list(set(area_ids).symmetric_difference(set(self.state.upf_dict.keys())))
        for el in temp:
            if el not in self.state.upf_dict.keys():
                self._create_new_upf(int(el))
            else:
                self._destroy_upf(int(el))

    def update_core_values(self):
        """
        Update core values.

        """
        self.state.oai_config_values.coreconfig.amf.served_guami_list.clear()
        oai_utils.add_served_guami_list_item(config=self.state.oai_config_values.coreconfig, mcc=self.state.mcc, mnc=self.state.mnc)

        self.state.oai_config_values.oai_smf.hostAliases.clear()
        self.state.oai_config_values.coreconfig.smf.upfs.clear()
        self.state.oai_config_values.coreconfig.snssais.clear()
        self.state.oai_config_values.coreconfig.amf.plmn_support_list.clear()
        self.state.oai_config_values.coreconfig.smf.smf_info.sNssaiSmfInfoList.clear()
        self.state.oai_config_values.coreconfig.smf.local_subscription_infos.clear()
        self.state.oai_config_values.coreconfig.dnns.clear()

        for sub_area in self.state.config_model.areas:

            ip_upf = self.call_external_function(self.state.upf_dict[str(sub_area.id)], "get_ip")
            oai_utils.add_host_aliases(self.state.oai_config_values.oai_smf, sub_area.id, ip_upf)
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
            self.state.oai_helm_chart,
            self.state.oai_config_values.model_dump(exclude_none=True, by_alias=True)
        )

    def _create_new_upf(self, area_id: int):
        """
        Create a UPF in a specified area.
        Args:
            area_id: area id to create UPF in.

        Returns: Blueprint ID of new UPF.

        """
        if str(area_id) not in self.state.upf_dict.keys():
            upfpayload = UPFBlueCreateModel(
                area_id=area_id,
                networks=BlueCreateModelNetworks(
                    mgt=self.state.config_model.config.network_endpoints.mgt,
                    n6=self.state.config_model.config.network_endpoints.mgt,
                    n3=self.state.config_model.config.network_endpoints.wan,
                    n4=self.state.config_model.config.network_endpoints.wan
                )
            )
            bp_manager = get_blueprint_manager()
            upf_id = bp_manager.create_blueprint(msg=upfpayload, path="OpenAirInterfaceUpf", wait=True, parent_id=self.id)
            self.register_children(upf_id)
            self.state.upf_dict[str(area_id)] = upf_id

            return upf_id
        raise BlueprintNGException(f"UPF in area {area_id} already exists")

    def _destroy_upf(self, area_id: int):
        """
        Destroy the UPF in a specified area.
        Args:
            area_id: id of the UPF area to be destroyed.

        """
        if str(area_id) in self.state.upf_dict.keys():
            upf_id = self.state.upf_dict[str(area_id)]
            bp_manager = get_blueprint_manager()
            bp_manager.delete_blueprint(blueprint_id=upf_id)
            self.deregister_children(upf_id)
            del self.state.upf_dict[str(area_id)]
        else:
            raise BlueprintNGException(f"UPF in area {area_id} does not exist")

    def update_upfs_config(self):
        """
        Restart all UPFs with new config.

        """
        for area in self.state.config_model.areas:
            upf_payload = UpfPayloadModel(
                nrf_ip=self.state.nrf_ip,
                slices=[]
            )
            for _slice in area.slices:

                slice_payload = SliceModel(
                    id=_slice.sliceId,
                    type=_slice.sliceType,
                    dnnList=[]
                )

                sub_slice = self.get_slice(_slice.sliceId)
                for dnn in sub_slice.dnnList:
                    dnn_payload = DnnModel()

                    dnn_info = self.get_dnn(dnn)

                    dnn_payload.name = dnn_info.net_name
                    dnn_payload.cidr = dnn_info.pools[0].cidr
                    slice_payload.dnnList.append(dnn_payload)

                upf_payload.slices.append(slice_payload)

            self.call_external_function(self.state.upf_dict[str(area.id)], "configure", upf_payload)

    def update_gnbs_config(self):
        """
        Restart all GNBs with new config.

        """
        pdus = self.get_gnb_pdus()
        for pdu in pdus:
            GNBConfigurator = get_class_from_path(pdu.implementation)
            configurator_instance: UERANSIMPDUConfigurator = GNBConfigurator(pdu)

            slices = []
            for slice in list(filter(lambda x: x.id == pdu.area, self.state.config_model.areas))[0].slices:
                slices.append(UeransimSlice(sd=int(slice.sliceId, 16), sst=SstConvertion.to_int(slice.sliceType)))

            gnb_payload = UeransimBlueprintRequestConfigureGNB(
                area=pdu.area,
                tac=pdu.area,
                plmn=self.state.config_model.config.plmn,
                amf_ip=self.state.amf_ip,
                amf_port=38412,
                nssai=slices
            )
            configurator_instance.configure(gnb_payload)

    def add_dnn_to_conf(self, new_dnn: SubDataNets):
        """
        Add new SubDataNets to conf.
        Args:
            new_dnn: new dnn to add.

        """
        logger.info(f"Adding dnn: {new_dnn.dnn}")

        if any(dnn.dnn == new_dnn.dnn for dnn in self.state.config_model.config.network_endpoints.data_nets):
            raise BlueprintNGException(f"Dnn {new_dnn.dnn} already exist")

        self.state.config_model.config.network_endpoints.data_nets.append(new_dnn)

        self.update_upfs_deployments()
        self.update_core_values()
        self.update_core()
        self.update_upfs_config()
        self.update_gnbs_config()

    def del_dnn_from_conf(self, old_dnn: str):
        """
        Delete SubDataNets from conf.
        Args:
            old_dnn: old_dnn to delete.

        """
        logger.info(f"Deleting dnn: {old_dnn}")
        dnn = self.get_dnn(old_dnn)

        for _slice in self.state.config_model.config.sliceProfiles:
            for _dnn in _slice.dnnList:
                if _dnn == dnn.dnn:
                    raise BlueprintNGException(f"Dnn {old_dnn} cannot be deleted because there are slices that use it")

        self.state.config_model.config.network_endpoints.data_nets.remove(dnn)

        self.update_upfs_deployments()
        self.update_core_values()
        self.update_core()
        self.update_upfs_config()
        self.update_gnbs_config()

    def add_subscriber_to_conf(self, new_subscriber: SubSubscribers, initialization: bool):
        """
        Add new SubSubscribers obj to conf.
        Args:
            new_subscriber: new SubSubscribers to add.
            initialization: if true add subscriber to conf otherwise not, necessary to maintain consistency with MySQL DB.

        """
        logger.info(f"Adding user with imsi: {new_subscriber.imsi}")

        if not initialization and any(subscriber.imsi == new_subscriber.imsi for subscriber in self.state.config_model.config.subscribers):
            raise BlueprintNGException(f"Subscriber with {new_subscriber.imsi} already exist")

        subscriber_slice_idds = list(map(lambda x: str(x.sliceId), new_subscriber.snssai))
        if len(list(filter(lambda x: x.sliceId in subscriber_slice_idds, self.state.config_model.config.sliceProfiles))) == 0:
            raise BlueprintNGException(f"One or more slices of Subscriber with {new_subscriber.imsi} does not exist")

        if not initialization:
            self.state.config_model.config.subscribers.append(new_subscriber)

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
        self.logger.info(f"Deleting subscriber with imsi: {imsi}")
        self.get_subscriber(imsi)
        with httpx.Client(http1=False, http2=True, base_url=self.state.base_udr_url) as client:
            api_url = f"/{imsi}/authentication-data/authentication-subscription"
            response = client.delete(api_url)
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Response content: {response.text}")

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
            api_url_sms = f"/{imsi}/{self.state.config_model.config.plmn}/provisioned-data/sm-data"
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
                api_url = f"/{imsi}/{self.state.config_model.config.plmn}/provisioned-data/sm-data"
                response = client.delete(api_url, params={'sst': sms.sst, 'sd': sms.sd})
                logger.info(f"Status code: {response.status_code}")
                logger.info(f"Response content: {response.text}")

            self.state.ue_dict[imsi].remove(sms)
            if len(self.state.ue_dict[imsi]) == 0:
                del self.state.ue_dict[imsi]

    def add_slice_to_conf(self, add_slice_model: Core5GAddSliceModel, oss: bool):
        """
        Add new SubSliceProfiles to conf.
        Args:
            add_slice_model: new SubSliceProfiles to add.
            oss: if False a slice can be added with an unspecified area id otherwise not.

        """
        self.logger.info(f"Adding Slice with ID: {add_slice_model.sliceId}")

        new_slice: SubSliceProfiles = SubSliceProfiles.model_validate(add_slice_model.model_dump(by_alias=True))
        if any(sub_slice.sliceId == new_slice.sliceId for sub_slice in self.state.config_model.config.sliceProfiles):
            raise BlueprintNGException(f"Slice {new_slice.sliceId} already exist")

        if oss and not add_slice_model.area_ids:
            raise BlueprintNGException(f"In OSS mode 'area_ids' need to be specified")

        if add_slice_model.area_ids:
            if len(add_slice_model.area_ids) == 1 and add_slice_model.area_ids == "*":
                for area in self.state.config_model.areas:
                    area.slices.append(SubSlices(
                        sliceType=new_slice.sliceType,
                        sliceId=new_slice.sliceId
                    ))
            else:
                for _id in add_slice_model.area_ids:
                    area = self.get_area(int(_id))
                    if not area:
                        raise BlueprintNGException(f"Unable to add slice: area '{_id}' does not exist")

                for _id in add_slice_model.area_ids:
                    area = self.get_area(int(_id))
                    area.slices.append(SubSlices(
                        sliceType=new_slice.sliceType,
                        sliceId=new_slice.sliceId
                    ))
        else:
            self.logger.warning("Adding Slice without areas association")

        self.state.config_model.config.sliceProfiles.append(new_slice)

        self.update_upfs_deployments()
        self.update_core_values()
        self.update_core()
        self.update_upfs_config()
        self.update_gnbs_config()

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

        for subscriber in self.state.config_model.config.subscribers:
            for _slice in self.state.ue_dict[subscriber.imsi].copy():
                if hex(int(_slice.sd))[2:].zfill(6) == update_slice_model.sliceId:
                    _subscribers.append(subscriber)

        self.state.config_model.config.sliceProfiles.remove(old_slice)
        self.state.config_model.config.sliceProfiles.append(update_slice_model)

        for subscriber in _subscribers:
            self.disassociating_subscriber_from_slice(subscriber.imsi)
            self.associating_subscriber_with_slice(subscriber.imsi)

        self.update_upfs_deployments()
        self.update_core_values()
        self.update_core()
        self.update_upfs_config()
        self.update_gnbs_config()

    def del_slice_from_conf(self, slice_id: str):
        """
        Delete SubSliceProfiles from conf.
        Args:
            slice_id: slice id of slice to delete.

        """
        self.logger.info(f"Deleting Slice with ID: {slice_id}")
        slice_to_delete = self.get_slice(slice_id)

        self.state.config_model.config.sliceProfiles.remove(slice_to_delete)
        for area in self.state.config_model.areas:
            for _slice in area.slices.copy():
                if _slice.sliceId == slice_to_delete.sliceId:
                    area.slices.remove(_slice)

        for imsi in self.state.ue_dict.keys():
            for ue_slice in self.state.ue_dict[imsi].copy():
                if slice_id == ue_slice.sd:
                    self.disassociating_subscriber_from_slice(imsi)

        self.update_upfs_deployments()
        self.update_core_values()
        self.update_core()
        self.update_upfs_config()
        self.update_gnbs_config()

    def get_slice(self, slice_id: str) -> SubSliceProfiles:
        """
        Get SubSliceProfiles with specified slice_id from conf.
        Args:
            slice_id: slice id of the slice to retrieve.

        Returns: the slice with specified slice_id.

        """
        for _slice in self.state.config_model.config.sliceProfiles:
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
        for _subscriber in self.state.config_model.config.subscribers:
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
        for area in self.state.config_model.areas:
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
        for area in self.state.config_model.areas:
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
        for dnn in self.state.config_model.config.network_endpoints.data_nets:
            if dnn_name == dnn.dnn:
                return dnn
        raise ValueError(f'Dnn {dnn_name} not found.')

    # @add_route(OAI_CORE_BLUE_TYPE, "/attach_gnb", [HttpRequestType.PUT], rest_attach_gnb)
    # def attach_gnb(self, gnb: Core5GAttachGNBModel):
    #     area = self.get_area(gnb.area_id)
    #     gnb_payload = UeransimBlueprintRequestConfigureGNB(
    #         area=gnb.area_id,
    #         tac=gnb.area_id,
    #         plmn=self.state.config_model.config.plmn,
    #         amf_ip=self.state.amf_ip,
    #         amf_port=38412,
    #         nssai=[]
    #     )
    #
    #     for slice in area.slices:
    #         slice_gnb = UeransimSlice(
    #             sd=int(slice.sliceId, 16),
    #             sst=SstConvertion.to_int(slice.sliceType)
    #         )
    #         gnb_payload.nssai.append(slice_gnb)
    #
    #     self.call_external_function(gnb.gnb_blue_id, "configure_gnb", gnb_payload)

    @day2_function("/add_subscriber", [HttpRequestType.PUT])
    def add_ues(self, subscriber_model: SubSubscribers, inizialization=False):
        """
        Calls OAI api to add new UE and his SMS (Session Management Subscription) to DB.
        Args:
            subscriber_model: SubSubscribers to add.
            inizialization: if true add subscriber to conf otherwise not, necessary to maintain consistency with MySQL DB.

        """
        self.add_subscriber_to_conf(subscriber_model, inizialization)
        self.associating_subscriber_with_slice(subscriber_model.imsi)

    @day2_function("/del_subscriber", [HttpRequestType.PUT])
    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        """
        Calls OAI api to delete an existing UE and all his related SMS from DB.
        Args:
            subscriber_model: SubSubscribers to remove.

        """
        # for _slice in self.state.ue_dict[subscriber_model.imsi]:
        self.disassociating_subscriber_from_slice(subscriber_model.imsi)
        self.del_subscriber_to_conf(subscriber_model.imsi)

    @day2_function("/add_slice_oss", [HttpRequestType.PUT])
    def _add_slice_oss(self, add_slice_model: Core5GAddSliceModel):
        """
        Add slice as OSS, if area is not provided an exception will be thrown.
        Args:
            add_slice_model: SubSliceProfiles to add.

        """
        self.add_slice_to_conf(add_slice_model, oss=True)

    @day2_function( "/add_slice_operator", [HttpRequestType.PUT])
    def _add_slice_operator(self, add_slice_model: Core5GAddSliceModel):
        """
        Add slice as Operator, area is not necessary for the slice to be added.
        Args:
            add_slice_model: SubSliceProfiles to add.

        """
        self.add_slice_to_conf(add_slice_model, oss=False)

    @day2_function( "/update_slice", [HttpRequestType.PUT])
    def _update_slice(self, update_slice_model: Core5GUpdateSliceModel):
        """
        Update slice.
        Args:
            update_slice_model: SubSliceProfiles to update.

        """
        self.update_slice(update_slice_model)

    @day2_function("/del_slice", [HttpRequestType.PUT])
    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        """
        Delete SubSliceProfiles from conf.
        Args:
            del_slice_model: SubSliceProfiles to delete.

        """
        self.del_slice_from_conf(del_slice_model.sliceId)

    @day2_function("/add_tac", [HttpRequestType.PUT])
    def add_tac(self, area: Core5GAddTacModel):
        """
        Add new SubArea to conf.
        Args:
            area: SubArea to add.

        """
        self.logger.info(f"Adding Area with ID: {area.id}")
        if any(_area.id == area.id for _area in self.state.config_model.areas):
            raise BlueprintNGException(f"Area with ID {area.id} already exist")

        self.state.config_model.areas.append(area)

        self.update_upfs_deployments()
        self.update_core_values()
        self.update_core()
        self.update_upfs_config()
        self.update_gnbs_config()

    @day2_function("/del_tac", [HttpRequestType.PUT])
    def del_tac(self, area: Core5GDelTacModel):
        """
        Delete SubArea from conf.
        Args:
            area: SubArea to delete.

        """
        self.logger.info(f"Deleting Area with ID: {area.id}")
        area = self.get_area(area.id)

        self.state.config_model.areas.remove(area)

        self.update_upfs_deployments()
        self.update_core_values()
        self.update_core()
        self.update_upfs_config()
        self.update_gnbs_config()

    @day2_function("/add_dnn", [HttpRequestType.PUT])
    def add_dnn(self, dnn: Core5GAddDnnModel):
        """
        Add new SubDataNets to conf.
        Args:
            dnn:SubDataNets to add.

        """
        self.add_dnn_to_conf(dnn)

    @day2_function("/del_dnn", [HttpRequestType.PUT])
    def del_dnn(self, dnn: Core5GDelDnnModel):
        """
        Delete SubDataNets from conf.
        Args:
            dnn: SubDataNets to delete.

        """
        self.del_dnn_from_conf(dnn.dnn)
