import copy
from abc import abstractmethod
from typing import Generic, TypeVar, Optional, List, final

from pydantic import Field

from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState, BlueprintNGException
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import day2_function
from nfvcl.blueprints_ng.pdu_configurators.ueransim_pdu_configurator import UERANSIMPDUConfigurator
from nfvcl.blueprints_ng.utils import get_class_from_path
from nfvcl.models.blueprint_ng.core5g.common import Create5gModel, SubSubscribers, SubSliceProfiles, SubSlices, SstConvertion
from nfvcl.models.blueprint_ng.g5.core import Core5GAddSubscriberModel, Core5GDelSubscriberModel, Core5GAddSliceModel, \
    Core5GDelSliceModel, Core5GAddTacModel, Core5GDelTacModel
from nfvcl.models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestConfigureGNB, UeransimSlice
from nfvcl.models.http_models import HttpRequestType
from nfvcl.models.network import PduModel

from nfvcl.topology.topology import build_topology


class Generic5GBlueprintNGState(BlueprintNGState):
    current_config: Optional[Create5gModel] = Field(default=None)

StateTypeVar5G = TypeVar("StateTypeVar5G", bound=Generic5GBlueprintNGState)
CreateConfigTypeVar5G = TypeVar("CreateConfigTypeVar5G")


class Generic5GBlueprintNG(BlueprintNG[Generic5GBlueprintNGState, Create5gModel], Generic[StateTypeVar5G, CreateConfigTypeVar5G]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GBlueprintNGState] = StateTypeVar5G):
        super().__init__(blueprint_id, state_type)

    @final
    def create(self, create_model: Create5gModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.pre_creation_checks()
        self.create_5g(create_model)

    @abstractmethod
    def create_5g(self, create_model: Create5gModel):
        pass

    @abstractmethod
    def get_amf_ip(self) -> str:
        pass

    @property
    def state(self) -> StateTypeVar5G:
        return super().state

    def pre_creation_checks(self):
        self.get_gnb_pdus()

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
                slices.append(UeransimSlice(sd=slice.sliceId, sst=SstConvertion.to_int(slice.sliceType)))

            gnb_configuration_request = UeransimBlueprintRequestConfigureGNB(
                area=pdu.area,
                plmn=self.state.current_config.config.plmn,
                tac=pdu.area,
                amf_ip=self.get_amf_ip(),
                amf_port=38412,
                nssai=slices
            )

            configurator_instance.configure(gnb_configuration_request)


    @abstractmethod
    def add_ues(self, subscriber_model: Core5GAddSubscriberModel):
        pass

    @day2_function("/add_ues", [HttpRequestType.PUT])
    def day2_add_ues(self, subscriber_model: Core5GAddSubscriberModel):
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

    @abstractmethod
    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        pass

    @day2_function("/del_ues", [HttpRequestType.PUT])
    def day2_del_ues(self, subscriber_model: Core5GDelSubscriberModel):
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

    def day2_add_slice_generic(self, add_slice_model: Core5GAddSliceModel, oss: bool):
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

    @abstractmethod
    def add_slice(self, add_slice_model: Core5GAddSliceModel, oss: bool):
        pass

    @day2_function("/add_slice_oss", [HttpRequestType.PUT])
    def day2_add_slice_oss(self, add_slice_model: Core5GAddSliceModel):
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

    @abstractmethod
    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        pass

    @day2_function("/del_slice", [HttpRequestType.PUT])
    def day2_del_slice(self, del_slice_model: Core5GDelSliceModel):
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


    @abstractmethod
    def add_tac(self, add_area_model: Core5GAddTacModel):
        pass

    @day2_function("/add_tac", [HttpRequestType.PUT])
    def day2_add_tac(self, add_area_model: Core5GAddTacModel):
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

    @abstractmethod
    def del_tac(self, del_area_model: Core5GDelTacModel):
        pass

    @day2_function("/del_tac", [HttpRequestType.PUT])
    def day2_del_tac(self, del_area_model: Core5GDelTacModel):
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


