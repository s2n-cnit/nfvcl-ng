from __future__ import annotations

import copy
from typing import Optional, Dict, List

from pydantic import Field
from starlette.requests import Request

from blueprints.blue_5g_base.models import Create5gModel
from blueprints.blue_5g_base.models.blue_5g_model import SubSubscribers, SubSliceProfiles, SubSlices
from blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState, BlueprintNGException
from blueprints_ng.lcm.blueprint_route_manager import add_route
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.modules.sdcore.sdcore_default_config import default_config
from blueprints_ng.modules.sdcore.sdcore_values_model import SDCoreValuesModel, SimAppYamlConfiguration
from blueprints_ng.modules.sdcore_upf.sdcore_upf_blueprint import SdCoreUPFCreateModel
from blueprints_ng.pdu_configurators.ueransim_pdu_configurator import UERANSIMPDUConfigurator
from blueprints_ng.resources import HelmChartResource
from blueprints_ng.utils import get_class_from_path
from models.base_model import NFVCLBaseModel
from models.blueprint_ng.g5.core import Core5GAddSubscriberModel, Core5GDelSubscriberModel, \
    Core5GAddSliceModel, Core5GDelSliceModel, Core5GAddTacModel, Core5GDelTacModel
from models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestConfigureGNB, UeransimSlice
from models.blueprint_ng.g5.upf import BlueCreateModelNetworks
from models.http_models import HttpRequestType
from models.network import PduModel
from rest_endpoints.blue_ng_router import get_blueprint_manager
from topology.topology import build_topology

SDCORE_BLUE_TYPE = "sdcore"


class BlueSDCoreCreateModel(Create5gModel):
    type: str = Field(default=SDCORE_BLUE_TYPE)

    def get_area(self, area_id: int):
        for area in self.areas:
            if area.id == area_id:
                return area
        return None


class SDCoreEdgeInfo(NFVCLBaseModel):
    blue_id: str = Field()
    n4_ip: str = Field()


class SdCoreBlueprintNGState(BlueprintNGState):
    sdcore_helm_chart: Optional[HelmChartResource] = Field(default=None)
    current_config: Optional[BlueSDCoreCreateModel] = Field(default=None)
    sdcore_config_values: Optional[SDCoreValuesModel] = Field(default=None)
    edge_areas: Dict[str, Dict[str, SDCoreEdgeInfo]] = Field(default_factory=dict)


@declare_blue_type(SDCORE_BLUE_TYPE)
class SdCoreBlueprintNG(BlueprintNG[SdCoreBlueprintNGState, BlueSDCoreCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = SdCoreBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    @property
    def config_ref(self) -> SimAppYamlConfiguration:
        return self.state.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration

    def check_model(self, model: BlueSDCoreCreateModel):
        self.get_gnb_pdus()

    def create(self, create_model: BlueSDCoreCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of example blueprint")

        self.state.sdcore_config_values = copy.deepcopy(default_config)
        self.state.current_config = copy.deepcopy(create_model)

        self.check_model(create_model)

        self.update_upf_deployments()
        self.update_sdcore_values()

        self.state.sdcore_helm_chart = HelmChartResource(
            area=list(filter(lambda x: x.core == True, self.state.current_config.areas))[0].id,
            name=f"sdcore",
            chart="helm_charts/charts/sdcore-0.13.2.tgz",
            chart_as_path=True,
            namespace=self.id
        )
        self.register_resource(self.state.sdcore_helm_chart)
        self.provider.install_helm_chart(self.state.sdcore_helm_chart, self.state.sdcore_config_values.model_dump_for_helm())

        self.update_gnb_config()

        # self.state.sdcore_config_values.omec_sub_provision.images.pull_policy = "Always"

        self.logger.debug(f"IP AMF: {self.state.sdcore_helm_chart.services['amf'].external_ip[0]}")

    def deploy_upf(self, area_id: int, dnn: str):
        """
        Deploy a UPF in the given area for the given dnn
        Args:
            area_id: Area in which the UPF will be deployed
            dnn: DNN that the UPF will serve
        """
        upf_networks = BlueCreateModelNetworks(
            mgt=self.state.current_config.config.network_endpoints.mgt,
            n4=self.state.current_config.config.network_endpoints.wan,
            n3=self.state.current_config.config.network_endpoints.n3,
            n6=self.state.current_config.config.network_endpoints.n6
        )

        dnn_ip_pool = list(filter(lambda x: x.dnn == dnn, self.state.current_config.config.network_endpoints.data_nets))[0].pools[0].cidr

        sdcore_upf_create_model = SdCoreUPFCreateModel(
            area_id=area_id,
            networks=upf_networks,
            dnn=dnn,
            gnb_n3_ip="PLACEHOLDER",
            gnb_n3_mac="PLACEHOLDER",
            start=False,
            ue_ip_pool_cidr=dnn_ip_pool
        )

        sdcore_upf_id = get_blueprint_manager().create_blueprint(sdcore_upf_create_model, "sdcore_upf", wait=True, parent_id=self.id)
        self.register_children(sdcore_upf_id)
        upf_n4_ip = self.call_external_function(sdcore_upf_id, "get_n4_info")
        sdcore_edge_info = SDCoreEdgeInfo(blue_id=sdcore_upf_id, n4_ip=upf_n4_ip)

        area_dict = self.state.edge_areas[str(area_id)]
        if not area_dict:
            area_dict = {}
        area_dict[dnn] = sdcore_edge_info
        self.state.edge_areas[str(area_id)] = area_dict

    def undeploy_upf(self, area_id: int, dnn: str):
        """
        Remove a deployed UPF
        Args:
            area_id: Area of the UPF to undeploy
            dnn: DNN of the UPF to undeploy
        """
        blue_id = self.state.edge_areas[str(area_id)][dnn].blue_id
        get_blueprint_manager().delete_blueprint(blue_id, wait=True)
        self.deregister_children(blue_id)
        del self.state.edge_areas[str(area_id)][dnn]

    def update_sdcore_values(self):
        """
        Update the SD-Core values from the current config present in the state
        This will also set the UPFs IPs on the slices
        """
        self.config_ref.from_generic_5g_model(self.state.current_config)

        for area in self.state.current_config.areas:
            for slice in area.slices:
                dnn = list(filter(lambda x: x.sliceId == slice.sliceId, self.state.current_config.config.sliceProfiles))[0].dnnList[0]
                sdcore_edge_info = self.state.edge_areas[str(area.id)][dnn]
                self.logger.debug(f"Setting UPF for slice {slice}: {sdcore_edge_info.n4_ip}")
                self.config_ref.set_upf_ip(slice.sliceId, sdcore_edge_info.n4_ip)

    def update_core(self):
        """
        Update the configuration of the deployed core
        """
        self.provider.update_values_helm_chart(self.state.sdcore_helm_chart, self.state.sdcore_config_values.model_dump_for_helm())

    def update_upf_deployments(self):
        """
        Update the UPF deployments to match the current configuration
        this will undeploy the ones that are not needed anymore and add new ones
        """
        for area in self.state.current_config.areas:
            if str(area.id) not in self.state.edge_areas:
                self.state.edge_areas[str(area.id)] = {}

            dnns_to_deploy_in_area = []
            for slice in area.slices:
                dnn = list(filter(lambda x: x.sliceId == slice.sliceId, self.state.current_config.config.sliceProfiles))[0].dnnList[0]
                dnns_to_deploy_in_area.append(dnn)

            dnns_to_deploy_in_area = list(set(dnns_to_deploy_in_area))

            for dnn in list(self.state.edge_areas[str(area.id)].keys()):
                if dnn not in dnns_to_deploy_in_area:
                    self.logger.info(f"Undeploying UPF for dnn '{dnn}' in area '{area.id}'")
                    self.undeploy_upf(area.id, dnn)

            for dnn in dnns_to_deploy_in_area:
                if dnn not in list(self.state.edge_areas[str(area.id)].keys()):
                    self.logger.info(f"Deploying UPF for dnn '{dnn}' in area '{area.id}'")
                    self.deploy_upf(area.id, dnn)

    def get_gnb_pdus(self) -> List[PduModel]:
        """
        Get the list of PDUs for the GNBs that need to be connected to this core instance

        Returns: List of PDUs
        """
        # TODO it only support UERANSIM now
        pdus = build_topology().get_pdus()
        ueransim_pdus = list(filter(lambda x: x.type == "UERANSIM", pdus))

        areas = list(map(lambda x: x.id, self.state.current_config.areas))

        pdus_to_return = []

        for area in areas:
            found_pdus = list(filter(lambda x: x.area == area, ueransim_pdus))
            if len(found_pdus) == 0:
                raise BlueprintNGException(f"No GNB PDU found for area '{area}'")
            if len(found_pdus) > 1:
                raise BlueprintNGException(f"More than 1 GNB PDU found for area '{area}'")
            pdus_to_return.append(found_pdus[0])

        return pdus_to_return

    def update_gnb_config(self):
        pdus = self.get_gnb_pdus()
        for pdu in pdus:
            GNBConfigurator = get_class_from_path(pdu.implementation)
            configurator_instance: UERANSIMPDUConfigurator = GNBConfigurator(pdu)

            gnb_n3_info = configurator_instance.get_n3_info()

            for upf_info in self.state.edge_areas[str(pdu.area)].values():
                self.call_external_function(upf_info.blue_id, "set_gnb_info", gnb_n3_info)

            # TODO nci is calculated with tac, is this correct?

            slices = []
            for slice in list(filter(lambda x: x.id == pdu.area, self.state.current_config.areas))[0].slices:
                slices.append(UeransimSlice(sd=slice.sliceId, sst=1))  # TODO get slice type

            gnb_configuration_request = UeransimBlueprintRequestConfigureGNB(
                area=pdu.area,
                plmn=self.state.current_config.config.plmn,
                tac=pdu.area,
                amf_ip=self.state.sdcore_helm_chart.services['amf'].external_ip[0],
                amf_port=38412,
                nssai=slices
            )

            configurator_instance.configure(gnb_configuration_request)

    @classmethod
    def rest_create(cls, msg: BlueSDCoreCreateModel, request: Request):
        return cls.api_day0_function(msg, request)

    # @classmethod
    # def attach_gnb_endpoint(cls, msg: Core5GAttachGNBModel, blue_id: str, request: Request):
    #     return cls.api_day2_function(msg, blue_id, request)
    #
    # @add_route(SDCORE_BLUE_TYPE, "/attach_gnb", [HttpRequestType.PUT], attach_gnb_endpoint)
    # def attach_gnb(self, model: Core5GAttachGNBModel):
    #     gnb_n3_info = self.call_external_function(model.gnb_blue_id, "get_n3_info", model.area_id)
    #     for upf_id in self.state.edge_areas[str(model.area_id)]:
    #         self.call_external_function(upf_id, "set_gnb_info", gnb_n3_info)
    #
    #     # TODO nci is calculated with tac, is this correct?
    #
    #     slices = []
    #     for slice in list(filter(lambda x:x.id == model.area_id, self.state.current_config.areas))[0].slices:
    #         slices.append(UeransimSlice(sd=slice.sliceId, sst=1)) # TODO get slice type
    #
    #     gnb_configuration_request = UeransimBlueprintRequestConfigureGNB(
    #         area=model.area_id,
    #         plmn=self.state.current_config.config.plmn,
    #         tac=model.area_id,
    #         amf_ip=self.state.sdcore_helm_chart.services['amf'].external_ip[0],
    #         amf_port=38412,
    #         nssai=slices
    #     )
    #
    #     self.call_external_function(model.gnb_blue_id, "configure_gnb", gnb_configuration_request)

    @classmethod
    def add_ues_endpoint(cls, msg: Core5GAddSubscriberModel, blue_id: str, request: Request):
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(SDCORE_BLUE_TYPE, "/add_ues", [HttpRequestType.PUT], add_ues_endpoint)
    def add_ues(self, subscriber_model: Core5GAddSubscriberModel):
        self.logger.info(f"Adding UE with IMSI: {subscriber_model.imsi}")
        # self.config_ref.add_subscriber_from_generic_model(subscriber_model)
        self.state.current_config.config.subscribers.append(SubSubscribers.model_validate(subscriber_model.model_dump(by_alias=True)))
        self.update_sdcore_values()
        self.update_core()

    @classmethod
    def del_ues_endpoint(cls, msg: Core5GDelSubscriberModel, blue_id: str, request: Request):
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(SDCORE_BLUE_TYPE, "/del_ues", [HttpRequestType.PUT], del_ues_endpoint)
    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        self.logger.info(f"Deleting UE with IMSI: {subscriber_model.imsi}")
        # self.config_ref.delete_subscriber(subscriber_model.imsi)
        self.state.current_config.config.subscribers = list(filter(lambda x: x.imsi != subscriber_model.imsi, self.state.current_config.config.subscribers))
        self.update_sdcore_values()
        self.update_core()

    def add_slice(self, add_slice_model: Core5GAddSliceModel, oss: bool):
        self.logger.info(f"Adding Slice with ID: {add_slice_model.sliceId}")

        new_slice: SubSliceProfiles = SubSliceProfiles.model_validate(add_slice_model.model_dump(by_alias=True))
        if any(sub_slice.sliceId == new_slice.sliceId for sub_slice in self.state.current_config.config.sliceProfiles):
            raise BlueprintNGException(f"Slice {new_slice.sliceId} already exist")

        if oss and not add_slice_model.area_ids:
            raise BlueprintNGException(f"In OSS mode 'area_ids' need to be specified")

        if add_slice_model.area_ids:
            if len(add_slice_model.area_ids) == 1 and add_slice_model.area_ids == "*":
                for area in self.state.current_config.areas:
                    area.slices.append(SubSlices(
                        sliceType=new_slice.sliceType,
                        sliceId=new_slice.sliceId
                    ))
            else:
                for id in add_slice_model.area_ids:
                    area = self.state.current_config.get_area(int(id))
                    if not area:
                        raise BlueprintNGException(f"Unable to add slice: area '{id}' does not exist")

                for id in add_slice_model.area_ids:
                    area = self.state.current_config.get_area(int(id))
                    area.slices.append(SubSlices(
                        sliceType=new_slice.sliceType,
                        sliceId=new_slice.sliceId
                    ))
        else:
            self.logger.warning("Adding Slice without areas association")

        self.state.current_config.config.sliceProfiles.append(new_slice)

        self.update_upf_deployments()
        self.update_gnb_config()
        self.update_sdcore_values()
        self.update_core()

    @classmethod
    def add_slice_oss_endpoint(cls, msg: Core5GAddSliceModel, blue_id: str, request: Request):
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(SDCORE_BLUE_TYPE, "/add_slice_oss", [HttpRequestType.PUT], add_slice_oss_endpoint)
    def add_slice_oss(self, add_slice_model: Core5GAddSliceModel):
        self.add_slice(add_slice_model, True)

    @classmethod
    def add_slice_operator_endpoint(cls, msg: Core5GAddSliceModel, blue_id: str, request: Request):
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(SDCORE_BLUE_TYPE, "/add_slice_operator", [HttpRequestType.PUT], add_slice_operator_endpoint)
    def add_slice_operator(self, add_slice_model: Core5GAddSliceModel):
        self.add_slice(add_slice_model, False)

    @classmethod
    def del_slice_endpoint(cls, msg: Core5GDelSliceModel, blue_id: str, request: Request):
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(SDCORE_BLUE_TYPE, "/del_slice", [HttpRequestType.PUT], del_slice_endpoint)
    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        self.logger.info(f"Deleting Slice with ID: {del_slice_model.sliceId}")
        # self.config_ref.delete_slice(del_slice_model.sliceId)

        # Delete slice from areas
        for area in self.state.current_config.areas:
            area.slices = list(filter(lambda x: x.sliceId != del_slice_model.sliceId, area.slices))

        # Delete slice from profiles
        self.state.current_config.config.sliceProfiles = list(filter(lambda x: x.sliceId != del_slice_model.sliceId, self.state.current_config.config.sliceProfiles))

        # TODO what about subscribers on this slice?

        self.update_upf_deployments()
        self.update_gnb_config()
        self.update_sdcore_values()
        self.update_core()

    @classmethod
    def add_tac_endpoint(cls, msg: Core5GAddTacModel, blue_id: str, request: Request):
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(SDCORE_BLUE_TYPE, "/add_tac", [HttpRequestType.PUT], add_tac_endpoint)
    def add_tac(self, add_area_model: Core5GAddTacModel):
        self.logger.info(f"Adding Area with ID: {add_area_model.id}")

        if self.state.current_config.get_area(add_area_model.id):
            raise BlueprintNGException(f"Area {add_area_model.id} already exist")

        self.state.current_config.areas.append(add_area_model)

        self.update_upf_deployments()
        self.update_gnb_config()
        self.update_sdcore_values()
        self.update_core()

    @classmethod
    def del_tac_endpoint(cls, msg: Core5GDelTacModel, blue_id: str, request: Request):
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(SDCORE_BLUE_TYPE, "/del_tac", [HttpRequestType.PUT], del_tac_endpoint)
    def del_tac(self, del_area_model: Core5GDelTacModel):
        self.logger.info(f"Deleting Area with ID: {del_area_model.areaId}")

        if not self.state.current_config.get_area(del_area_model.areaId):
            raise BlueprintNGException(f"Area {del_area_model.areaId} not found")

        self.state.current_config.areas = list(filter(lambda x: x.id != del_area_model.areaId, self.state.current_config.areas))

        self.update_upf_deployments()
        self.update_gnb_config()
        self.update_sdcore_values()
        self.update_core()
