import copy
from abc import abstractmethod
from typing import Generic, TypeVar, Optional, List, final, Dict, Set

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import DeployedUPFInfo
from nfvcl.blueprints_ng.pdu_configurators.types.gnb_pdu_configurator import GNBPDUConfigurator
from nfvcl.models.blueprint_ng.core5g.common import Create5gModel, SubSubscribers, SubSliceProfiles, SubSlices, \
    SstConvertion, SubDataNets, NetworkEndPointWithType
from nfvcl.models.blueprint_ng.g5.core import Core5GAddSubscriberModel, Core5GDelSubscriberModel, Core5GAddSliceModel, \
    Core5GDelSliceModel, Core5GAddTacModel, Core5GDelTacModel, Core5GAddDnnModel, Core5GDelDnnModel
from nfvcl.models.blueprint_ng.g5.upf import UPFBlueCreateModel, BlueCreateModelNetworks, SliceModel
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG, BlueprintNGState, BlueprintNGException
from nfvcl_core.blueprints.blueprint_type_manager import day2_function
from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.http_models import HttpRequestType
from nfvcl_core.models.linux.ip import Route
from nfvcl_core.models.network import PduModel
from nfvcl_core.models.network.ipam_models import SerializableIPv4Address, SerializableIPv4Network
from nfvcl_core.models.network.network_models import PduType, MultusInterface
from nfvcl_core.models.pdu.gnb import GNBPDUSlice, GNBPDUConfigure


class UPFInfo(NFVCLBaseModel):
    blue_id: str = Field()
    external: bool = Field()
    router_gnb_ip: Optional[SerializableIPv4Address] = Field(default=None)
    upf_list: List[DeployedUPFInfo] = Field(default_factory=list)
    current_config: UPFBlueCreateModel = Field()

class RANAreaInfo(NFVCLBaseModel):
    area: int = Field()
    pdu_names: List[str] = Field(default_factory=list)

class EdgeAreaInfo(NFVCLBaseModel):
    area: int = Field()
    upf: Optional[UPFInfo] = Field(default=None)

class NFNetworkEndpoint(NetworkEndPointWithType):
    """
    Used only in the 5g blueprints state
    """
    ip_address: Optional[SerializableIPv4Address] = Field(default=None)
    network_cidr: Optional[SerializableIPv4Network] = Field(default=None)
    multus: Optional[MultusInterface] = Field(default=None)

class NFNetworkEndpoints(NFVCLBaseModel):
    n2: Optional[NFNetworkEndpoint] = Field(default=None)
    n4: Optional[NFNetworkEndpoint] = Field(default=None)

class Generic5GBlueprintNGState(BlueprintNGState):
    current_config: Optional[Create5gModel] = Field(default=None)
    edge_areas: Dict[str, EdgeAreaInfo] = Field(default_factory=dict)
    ran_areas: Dict[str, RANAreaInfo] = Field(default_factory=dict)
    core_deployed: bool = Field(default=False)
    network_endpoints: Optional[NFNetworkEndpoints] = Field(default_factory=NFNetworkEndpoints)


StateTypeVar5G = TypeVar("StateTypeVar5G", bound=Generic5GBlueprintNGState)
CreateConfigTypeVar5G = TypeVar("CreateConfigTypeVar5G")

class Generic5GBlueprintNG(BlueprintNG[Generic5GBlueprintNGState, Create5gModel], Generic[StateTypeVar5G, CreateConfigTypeVar5G]):
    default_upf_implementation: Optional[str] = None

    def __init__(self, blueprint_id: str, state_type: type[Generic5GBlueprintNGState] = StateTypeVar5G):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5G:
        return super().state

    @final
    def create(self, create_model: Create5gModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.configuration_feasibility_check(create_model)
        self.pre_creation_checks()

        # Prepare the network for the 5G core
        self.prepare_network()
        # Update the edge areas creating the router (if needed) and the UPFs
        self.update_edge_areas()
        # Deploy the 5G core itself
        self.create_5g(create_model)
        # Wait for the core to be ready
        self.wait_core_ready()
        # Update the UPFs with new data gathered after the core deployment (like the NRF ip)
        self.update_edge_areas()
        # Update the attached GNBs
        self.update_gnb_config()
        self.logger.success("5G Blueprint completely deployed")

    def get_core_area_id(self) -> int:
        """
        Get the core area id

        Returns: Area id of the core
        """
        return int(list(filter(lambda x: x.core == True, self.state.current_config.areas))[0].id)

    def pre_creation_checks(self):
        """
        Make sure that the prerequisites for the blueprint are met
        This method should raise an exception if the prerequisites are not met
        """
        for pdu_model in self.get_gnb_pdus():
            if self.provider.is_pdu_locked(pdu_model):
                raise BlueprintNGException(f"GNB PDU {pdu_model.name} is already locked")

    def configuration_feasibility_check(self, config_model: Create5gModel):
        """
        Check if the config is feasible
        Args:
            config_model: Config model of which to check for feasibility
        """
        # Check multiple slices with the same DNN
        ddns = []
        for slice in config_model.config.sliceProfiles:
            ddns.extend(slice.dnnList)
        if len(list(set(ddns))) < len(ddns):
            raise BlueprintNGException("Cannot have multiple slices with the same DNN")

    @abstractmethod
    def prepare_network(self):
        pass

    @abstractmethod
    def create_5g(self, create_model: Create5gModel):
        pass

    @abstractmethod
    def update_core(self):
        pass

    @abstractmethod
    def get_amf_ip(self) -> str:
        pass

    @abstractmethod
    def get_nrf_ip(self) -> str:
        pass

    @abstractmethod
    def get_smf_ip(self) -> str:
        pass

    @abstractmethod
    def wait_core_ready(self):
        """
        Wait for the core to be ready for incoming GNB/UPF connections
        """
        pass

    ################################################################
    ####                  START EDGE SECTION                    ####
    ################################################################

    def update_edge_areas(self):
        """
        Deploy new edge areas
        Delete edge areas not needed anymore
        If necessary send update to changed edge areas
        """

        for area in self.state.current_config.areas:
            if str(area.id) not in self.state.edge_areas:
                self.state.edge_areas[str(area.id)] = EdgeAreaInfo(area=area.id)

                # UPF deployment for this area
                upf_info = self.deploy_upf_blueprint(area.id, area.upf.type if area.upf.type else self.default_upf_implementation)
                self.state.edge_areas[str(area.id)].upf = upf_info
            else:
                # The edge area is already deployed but MAY need to be updated with a new configuration
                edge_info = self.state.edge_areas[str(area.id)]

                # Updating UPF configuration (move to a new method in the future?)
                updated_config = self._create_upf_config(area.id)
                if edge_info.upf.current_config != updated_config:
                    self.logger.info(f"Updating UPF for area {area.id}")
                    self.provider.call_blueprint_function(edge_info.upf.blue_id, "update", updated_config)
                    self.state.edge_areas[str(area.id)].upf = self.get_upfs_info(area.id, edge_info.upf.blue_id, updated_config)

        # Deleting edge areas that are not in the current configuration (deleted by del_tac day2)
        currently_existing_areas: Set[str] = set(map(lambda x: str(x.id), self.state.current_config.areas))
        currently_deployed_edge_areas = set(self.state.edge_areas.keys())
        areas_to_delete = currently_deployed_edge_areas - currently_existing_areas
        for edge_area_id in areas_to_delete:
            # Undeploy upf blueprint
            self.undeploy_upf_blueprint(int(edge_area_id))

            # Delete edge area from state
            del self.state.edge_areas[edge_area_id]

    def _create_upf_config(self, area_id: int) -> UPFBlueCreateModel:
        """
        Create the UPF configuration for a specific area and dnn
        Args:
            area_id: Area of the UPF
        Returns: Model for the creation or update of an UPF blueprint
        """
        slices: List[SliceModel] = []

        for slice_profile in self.state.current_config.get_slices_profiles_for_area(area_id):
            slices.append(SliceModel.from_slice_profile(slice_profile, self.state.current_config.config.network_endpoints.data_nets))

        upf_create_model = UPFBlueCreateModel(
            area_id=area_id,
            networks=BlueCreateModelNetworks(
                mgt=self.state.current_config.config.network_endpoints.mgt,
                n4=self.state.current_config.config.network_endpoints.n4,
                n3=self.state.current_config.get_area(area_id).networks.n3,
                n6=self.state.current_config.get_area(area_id).networks.n6,
                gnb=self.state.current_config.get_area(area_id).networks.gnb
            ),
            slices=slices,
            start=True,
            nrf_ip=SerializableIPv4Address(self.get_nrf_ip()) if self.state.core_deployed else None,
            smf_ip=SerializableIPv4Address(self.get_smf_ip()) if self.state.core_deployed else None,
        )
        return upf_create_model

    def deploy_upf_blueprint(self, area_id: int, upf_type: str) -> UPFInfo:
        """
        Deploy a UPF in the given area
        Args:
            area_id: Area in which the UPF will be deployed
            upf_type: Type of the UPF blueprint to deploy
        """
        self.logger.info(f"Deploying UPF for area {area_id}")
        upf_create_model = self._create_upf_config(area_id)
        upf_id = self.provider.create_blueprint(upf_type, upf_create_model)
        self.register_children(upf_id)

        upf_info = self.get_upfs_info(area_id, upf_id, upf_create_model)
        self.logger.info(f"Deployed UPF for area {area_id}")

        return upf_info

    def get_upfs_info(self, area_id: int, upf_id: str, current_config: UPFBlueCreateModel) -> UPFInfo:
        """
        Get the current upfs info from the deployed blueprint
        Args:
            area_id: Area of the UPF
            upf_id: Blueprint ID of the UPF
            current_config: Current config of the UPF

        Returns: UPFInfo
        """
        upf_deployed_info: List[DeployedUPFInfo] = self.provider.call_blueprint_function(upf_id, "get_upfs_info")
        upf_info = UPFInfo(
            blue_id=upf_id,
            router_gnb_ip=upf_deployed_info[0].router_gnb_ip.exploded if upf_deployed_info[0].router_gnb_ip else None,
            external=False,
            upf_list=upf_deployed_info,
            current_config=current_config
        )
        return upf_info

    def undeploy_upf_blueprint(self, area_id: int):
        """
        Remove a deployed UPF
        Args:
            area_id: Area of the UPF to undeploy
        """
        self.logger.info(f"Deleting UPF for area {area_id}")
        blue_id = self.state.edge_areas[str(area_id)].upf.blue_id
        self.provider.delete_blueprint(blue_id)
        self.deregister_children(blue_id)
        self.logger.info(f"Deleted UPF for area {area_id}")

    def get_upfs_for_slice(self, slice_id: str) -> List[DeployedUPFInfo]:
        upf_list_for_slice: List[DeployedUPFInfo] = []
        for edge_area in self.state.edge_areas.values():
            for upf_deployed in edge_area.upf.upf_list:
                if len(list(filter(lambda x: x.id == slice_id.rjust(6, "0"), upf_deployed.served_slices))) > 0:
                    upf_list_for_slice.append(upf_deployed)
        return upf_list_for_slice

    ################################################################
    ####                   END EDGE SECTION                     ####
    ################################################################

    ################################################################
    ####                   START RAN SECTION                    ####
    ################################################################

    def get_gnb_pdus(self) -> List[PduModel]:
        """
        Get the list of PDUs for the GNBs that need to be connected to this core instance

        Returns: List of PDUs
        """
        pdu_models: List[PduModel] = []

        for area in self.state.current_config.areas:
            if area.gnb.configure:
                if not area.gnb.pduList:
                    pdu_models.extend(self.provider.find_pdus(area.id, PduType.GNB))
                else:
                    for pdu_name in area.gnb.pduList:
                        pdu_models.append(self.provider.find_pdu(area.id, PduType.GNB, name=pdu_name))
        return pdu_models

    def _additional_routes_for_gnb(self, area: str) -> List[Route]:
        """
        Generate a list of routes that need to be added to the GNB in the area
        Args:
            area: Area of the GNB
        Returns: List of routes to be added to the GNB
        """
        # upf_list[0] here is ok because every UPF deployed in the same area have the same n3 network

        upf: Optional[UPFInfo] = self.state.edge_areas[area].upf
        if not upf.router_gnb_ip:
            return []
        return [Route(
            network_cidr=upf.upf_list[0].network_info.n3_cidr.exploded,
            next_hop=upf.router_gnb_ip.exploded
        )]

    def update_gnb_config(self):
        """
        Update the GNBs config
        """
        for pdu in self.get_gnb_pdus():
            if not self.provider.is_pdu_locked_by_current_blueprint(pdu):
                self.provider.lock_pdu(pdu)
            configurator_instance: GNBPDUConfigurator = self.provider.get_pdu_configurator(pdu)

            # TODO nci is calculated with tac, is this correct?
            slices = []
            for slice in list(filter(lambda x: x.id == pdu.area, self.state.current_config.areas))[0].slices:
                slices.append(GNBPDUSlice(sd=slice.sliceId, sst=SstConvertion.to_int(slice.sliceType)))

            gnb_configuration_request = GNBPDUConfigure(
                area=pdu.area,
                plmn=self.state.current_config.config.plmn,
                tac=pdu.area,
                amf_ip=self.get_amf_ip(),
                upf_ip=self.get_upfs_for_slice(str(slices[0].sd))[0].network_info.n3_ip.exploded, # This is not really right, but it's needed for LiteON AIO
                amf_port=38412,
                nssai=slices,
                additional_routes=self._additional_routes_for_gnb(str(pdu.area))
            )

            configurator_instance.configure(gnb_configuration_request)
            if str(pdu.area) not in self.state.ran_areas:
                self.state.ran_areas[str(pdu.area)] = RANAreaInfo(area=pdu.area)
            self.state.ran_areas[str(pdu.area)].pdu_names.append(pdu.name)

        # Unlock PDUs for removed areas
        currently_existing_areas: Set[str] = set(map(lambda x: str(x.id), self.state.current_config.areas))
        currently_deployed_ran_areas = set(self.state.ran_areas.keys())
        areas_to_delete = currently_deployed_ran_areas - currently_existing_areas
        for ran_area_id in areas_to_delete:
            # Get information about the area that need to be deleted
            ran_area_info = self.state.ran_areas[ran_area_id]
            for pdu in ran_area_info.pdu_names:
                self.provider.unlock_pdu(self.provider.find_by_name(pdu))

            # Delete edge area from state
            del self.state.ran_areas[ran_area_id]

    ################################################################
    ####                    END RAN SECTION                     ####
    ################################################################

    ################################################################
    ####                   START DAY2 SECTION                   ####
    ################################################################

    @day2_function("/get_current_config", [HttpRequestType.GET])
    def day2_get_current_config(self) -> Create5gModel:
        """
        Get the current configuration of the blueprint
        """
        return self.state.current_config

    def add_ues(self, subscriber_model: Core5GAddSubscriberModel):
        self.update_core()

    @day2_function("/add_ues", [HttpRequestType.PUT])
    def day2_add_ues(self, subscriber_model: Core5GAddSubscriberModel):
        """
        Add a new UE to the core
        Args:
            subscriber_model: Model of the UE to add
        """
        self.logger.info(f"Adding UE with IMSI: {subscriber_model.imsi}")

        # Check if the subscriber already present
        if any(subscriber.imsi == subscriber_model.imsi for subscriber in self.state.current_config.config.subscribers):
            raise BlueprintNGException(f"Subscriber with {subscriber_model.imsi} already exist")

        # Check if the subscriber's slices are present
        subscriber_slice_idds = list(map(lambda x: str(x.sliceId), subscriber_model.snssai))
        if len(list(filter(lambda x: x.sliceId in subscriber_slice_idds, self.state.current_config.config.sliceProfiles))) == 0:
            raise BlueprintNGException(f"One or more slices of Subscriber with {subscriber_model.imsi} does not exist")

        backup_config = copy.deepcopy(self.state.current_config)

        self.state.current_config.config.subscribers.append(SubSubscribers.model_validate(subscriber_model.model_dump(by_alias=True)))

        try:
            self.add_ues(subscriber_model)
        except Exception as e:
            self.logger.exception(f"Error adding UE with IMSI: {subscriber_model.imsi}", exc_info=e)
            self.state.current_config = backup_config
            raise e

        self.logger.success(f"Added UE with IMSI: {subscriber_model.imsi}")

    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        self.update_core()

    @day2_function("/del_ues", [HttpRequestType.PUT])
    def day2_del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        """
        Delete a UE from the core
        Args:
            subscriber_model: Model of the UE to be deleted
        """
        self.logger.info(f"Deleting UE with IMSI: {subscriber_model.imsi}")

        # Check if the subscriber is present
        if not any(subscriber.imsi == subscriber_model.imsi for subscriber in self.state.current_config.config.subscribers):
            raise BlueprintNGException(f"Subscriber {subscriber_model.imsi} not found")

        backup_config = copy.deepcopy(self.state.current_config)

        self.state.current_config.config.subscribers = list(filter(lambda x: x.imsi != subscriber_model.imsi, self.state.current_config.config.subscribers))

        try:
            self.del_ues(subscriber_model)
        except Exception as e:
            self.logger.exception(f"Error deleting UE with IMSI: {subscriber_model.imsi}", exc_info=e)
            self.state.current_config = backup_config
            raise e

        self.logger.success(f"Deleted UE with IMSI: {subscriber_model.imsi}")

    @day2_function("/add_dnn", [HttpRequestType.PUT])
    def day2_add_dnn(self, dnn_model: Core5GAddDnnModel):
        """
        Add a new DNN to the core
        Args:
            dnn_model: Model of the DNN to add
        """
        self.logger.info(f"Adding DNN: {dnn_model.dnn}")

        # Check if the DNN already present
        if any(dnn.dnn == dnn_model.dnn for dnn in self.state.current_config.config.network_endpoints.data_nets):
            raise BlueprintNGException(f"DNN {dnn_model.dnn} already exist")

        backup_config = copy.deepcopy(self.state.current_config)

        self.state.current_config.config.network_endpoints.data_nets.append(SubDataNets.model_validate(dnn_model.model_dump(by_alias=True)))

        try:
            self.add_dnn(dnn_model)
        except Exception as e:
            self.logger.exception(f"Error adding DNN: {dnn_model.dnn}", exc_info=e)
            self.state.current_config = backup_config
            raise e

        self.logger.success(f"Added DNN: {dnn_model.dnn}")

    def add_dnn(self, dnn_model: Core5GAddDnnModel):
        self.update_core()

    @day2_function("/del_dnn", [HttpRequestType.PUT])
    def day2_del_dnn(self, del_dnn_model: Core5GDelDnnModel):
        """
        Delete a DNN from the core
        Args:
            del_dnn_model: Model of the UE to be deleted
        """
        self.logger.info(f"Deleting DNN: {del_dnn_model.dnn}")

        # Check if the DNN is present
        if not any(dnn.dnn == del_dnn_model.dnn for dnn in self.state.current_config.config.network_endpoints.data_nets):
            raise BlueprintNGException(f"DNN {del_dnn_model.dnn} not found")

        # Check if DNN is used by some slice
        for slice in self.state.current_config.config.sliceProfiles:
            if del_dnn_model.dnn in slice.dnnList:
                raise BlueprintNGException(f"DNN {del_dnn_model.dnn} present in slice {slice.sliceId}")

        backup_config = copy.deepcopy(self.state.current_config)

        self.state.current_config.config.network_endpoints.data_nets = list(filter(lambda x: x.dnn != del_dnn_model.dnn, self.state.current_config.config.network_endpoints.data_nets))

        try:
            self.del_dnn(del_dnn_model)
        except Exception as e:
            self.logger.exception(f"Error deleting DNN: {del_dnn_model.dnn}", exc_info=e)
            self.state.current_config = backup_config
            raise e

        self.logger.success(f"Deleted DNN: {del_dnn_model.dnn}")

    def del_dnn(self, del_dnn_model: Core5GDelDnnModel):
        self.update_core()

    def day2_add_slice_generic(self, add_slice_model: SubSliceProfiles, oss: bool):
        new_slice: SubSliceProfiles = SubSliceProfiles.model_validate(add_slice_model.model_dump(by_alias=True))

        # Create a copy of the config and update it to check if it's still correct
        tmp_updated_config = copy.deepcopy(self.state.current_config)
        tmp_updated_config.config.sliceProfiles.append(new_slice)
        self.configuration_feasibility_check(tmp_updated_config)

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

    def add_slice(self, add_slice_model: SubSliceProfiles, oss: bool):
        self.update_edge_areas()
        self.update_gnb_config()
        self.update_core()

    @day2_function("/add_slice_oss", [HttpRequestType.PUT])
    def day2_add_slice_oss(self, add_slice_model: SubSliceProfiles):
        """
        Add a new slice to the core, the area is required
        Args:
            add_slice_model: Model of the slice to add
        """
        self.logger.info(f"Adding Slice with ID: {add_slice_model.sliceId}")
        backup_config = copy.deepcopy(self.state.current_config)

        try:
            self.day2_add_slice_generic(add_slice_model, oss=True)
            self.add_slice(add_slice_model, True)
        except Exception as e:
            self.logger.exception(f"Error adding Slice with ID: {add_slice_model.sliceId}", exc_info=e)
            self.state.current_config = backup_config
            raise e

        self.logger.success(f"Added Slice with ID: {add_slice_model.sliceId}")

    @day2_function("/add_slice_operator", [HttpRequestType.PUT])
    def day2_add_slice_operator(self, add_slice_model: Core5GAddSliceModel):
        """
        Add a new slice to the core, the area is not required
        Args:
            add_slice_model: Model of the slice to add
        """
        self.logger.info(f"Adding Slice with ID: {add_slice_model.sliceId}")

        backup_config = copy.deepcopy(self.state.current_config)

        try:
            self.day2_add_slice_generic(add_slice_model, oss=False)
            self.add_slice(add_slice_model, False)
        except Exception as e:
            self.logger.exception(f"Error adding Slice with ID: {add_slice_model.sliceId}", exc_info=e)
            self.state.current_config = backup_config
            raise e

        self.logger.success(f"Added Slice with ID: {add_slice_model.sliceId}")

    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        self.update_edge_areas()
        self.update_gnb_config()
        self.update_core()

    @day2_function("/del_slice", [HttpRequestType.PUT])
    def day2_del_slice(self, del_slice_model: Core5GDelSliceModel):
        """
        Delete a slice from the core
        Args:
            del_slice_model: Model of the slice to be deleted
        """
        self.logger.info(f"Deleting Slice with ID: {del_slice_model.sliceId}")

        backup_config = copy.deepcopy(self.state.current_config)

        # Delete slice from areas
        for area in self.state.current_config.areas:
            area.slices = list(filter(lambda x: x.sliceId != del_slice_model.sliceId, area.slices))

        # Delete slice from profiles
        self.state.current_config.config.sliceProfiles = list(filter(lambda x: x.sliceId != del_slice_model.sliceId, self.state.current_config.config.sliceProfiles))

        # TODO what about subscribers on this slice?

        try:
            self.del_slice(del_slice_model)
        except Exception as e:
            self.logger.exception(f"Error deleting Slice with ID: {del_slice_model.sliceId}", exc_info=e)
            self.state.current_config = backup_config
            raise e

        self.logger.success(f"Deleted Slice with ID: {del_slice_model.sliceId}")

    def add_tac(self, add_area_model: Core5GAddTacModel):
        self.update_edge_areas()
        self.update_gnb_config()
        self.update_core()

    @day2_function("/add_tac", [HttpRequestType.PUT])
    def day2_add_tac(self, add_area_model: Core5GAddTacModel):
        """
        Add a new area to the core
        Args:
            add_area_model: Model of the area to add
        """
        self.logger.info(f"Adding Area with ID: {add_area_model.id}")

        backup_config = copy.deepcopy(self.state.current_config)

        if self.state.current_config.get_area(add_area_model.id):
            raise BlueprintNGException(f"Area {add_area_model.id} already exist")

        self.state.current_config.areas.append(add_area_model)

        try:
            self.add_tac(add_area_model)
        except Exception as e:
            self.logger.exception(f"Error adding Area with ID: {add_area_model.id}", exc_info=e)
            self.state.current_config = backup_config
            raise e

        self.logger.success(f"Added Area with ID: {add_area_model.id}")

    def del_tac(self, del_area_model: Core5GDelTacModel):
        self.update_edge_areas()
        self.update_gnb_config()
        self.update_core()

    @day2_function("/del_tac", [HttpRequestType.PUT])
    def day2_del_tac(self, del_area_model: Core5GDelTacModel):
        """
        Delete an area from the core
        Args:
            del_area_model: Model of the area to be deleted
        """
        self.logger.info(f"Deleting Area with ID: {del_area_model.areaId}")

        backup_config = copy.deepcopy(self.state.current_config)

        if not self.state.current_config.get_area(del_area_model.areaId):
            raise BlueprintNGException(f"Area {del_area_model.areaId} not found")

        self.state.current_config.areas = list(filter(lambda x: x.id != del_area_model.areaId, self.state.current_config.areas))

        try:
            self.del_tac(del_area_model)
        except Exception as e:
            self.logger.exception(f"Error deleting Area with ID: {del_area_model.areaId}", exc_info=e)
            self.state.current_config = backup_config
            raise e

        self.logger.success(f"Deleted Area with ID: {del_area_model.areaId}")

    ################################################################
    ####                    END DAY2 SECTION                    ####
    ################################################################
