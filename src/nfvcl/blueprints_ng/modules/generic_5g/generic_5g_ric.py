import copy
from abc import abstractmethod
from typing import Generic, TypeVar, Optional, final, List, Dict

from pydantic import Field

from nfvcl.blueprints_ng.pdu_configurators.types.gnb_pdu_configurator import GNBPDUConfigurator
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import day2_function
from nfvcl_core_models.blueprints.blueprint import BlueprintNGState
from nfvcl_core_models.network.network_models import PduType, PduLockType
from nfvcl_core_models.pdu.gnb import GNBPDURic
from nfvcl_models.blueprint_ng.g5.ric import RICBlueCreateModel, RICNetworkInfo, RICRunXappModel, RICOnboardXappModel, RicDeleteXappModel


class DeployedRICInfo(NFVCLBaseModel):
    area: int = Field()
    network_info: Optional[RICNetworkInfo] = Field(default=None)
    vm_resource_id: Optional[str] = Field(default=None)
    # vm_configurator_id: Optional[str] = Field(default=None)


class Generic5GRICBlueprintNGState(BlueprintNGState):
    current_config: Optional[RICBlueCreateModel] = Field(default=None)
    ric: Optional[DeployedRICInfo] = Field(default=None)
    gnb_ids: Optional[Dict[str, str]] = Field(default_factory=dict)
    xapps: List[str] = Field(default_factory=list)


StateTypeVar5GRIC = TypeVar("StateTypeVar5GRIC", bound=Generic5GRICBlueprintNGState)
CreateConfigTypeVar5GRIC = TypeVar("CreateConfigTypeVar5GRIC")


class Generic5GRICBlueprintNG(BlueprintNG[Generic5GRICBlueprintNGState, RICBlueCreateModel], Generic[StateTypeVar5GRIC, CreateConfigTypeVar5GRIC]):

    def __init__(self, blueprint_id: str, state_type: type[Generic5GRICBlueprintNGState] = StateTypeVar5GRIC):
        super().__init__(blueprint_id, state_type)

    def pre_creation_checks(self):
        pdu = self.provider.find_pdu(self.state.current_config.area_id, PduType.GNB, name=self.state.current_config.gnb_pdu_name)
        if pdu and self.provider.is_pdu_locked(pdu, PduLockType.RIC):
            raise ValueError(f"PDU {pdu.name} is already locked by another blueprint")

    @property
    def state(self) -> StateTypeVar5GRIC:
        return super().state

    @final
    def create(self, create_model: RICBlueCreateModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.pre_creation_checks()
        self.create_ric()
        self.update_ran()
        self.wait_gnb_connection()

    @abstractmethod
    def create_ric(self):
        pass

    def update_ran(self):
        """
        Update the GNBs config
        """
        self.logger.info("Update RAN")
        pdu = self.provider.find_pdu(self.state.current_config.area_id, PduType.GNB, name=self.state.current_config.gnb_pdu_name)
        if pdu:
            if not self.provider.is_pdu_locked_by_current_blueprint(pdu, PduLockType.RIC):
                self.provider.lock_pdu(pdu, PduLockType.RIC)
                configurator_instance: GNBPDUConfigurator = self.provider.get_pdu_configurator(pdu, PduLockType.RIC)
                gnb_configuration_request = GNBPDURic(
                    remote_ip=self.state.ric.network_info.e2_ip.exploded,
                    remote_port=self.state.current_config.port
                )
                configurator_instance.configure_ric(gnb_configuration_request)
                gnb_id = configurator_instance.get_gnb_id()
                self.state.gnb_ids[self.state.current_config.gnb_pdu_name] = gnb_id
        else:
            raise ValueError(f"Cannot find GNB PDU {self.state.current_config.gnb_pdu_name}")

    @final
    def update(self, create_model: RICBlueCreateModel):
        self.state.current_config = copy.deepcopy(create_model)
        self.update_ric()

    @abstractmethod
    def update_ric(self):
        pass

    @final
    def onboard_xapp(self, xapp_data: RICOnboardXappModel):
        # self.state.current_config = copy.deepcopy(create_model)
        self.onboard_xapp_ric(xapp_data)

    @abstractmethod
    def onboard_xapp_ric(self, xapp_data: RICOnboardXappModel):
        pass

    @final
    def run_xapp(self, xapp: RICRunXappModel):
        # self.state.current_config = copy.deepcopy(create_model)
        self.run_xapp_ric(xapp)

    @abstractmethod
    def run_xapp_ric(self, xapp: RICRunXappModel):
        pass

    @final
    def get_xapps(self):
        return self.get_xapps_ric()

    @abstractmethod
    def get_xapps_ric(self):
        pass

    @final
    def delete_xapp(self, xapp: RicDeleteXappModel):
        return self.delete_xapp_ric(xapp)

    @abstractmethod
    def delete_xapp_ric(self, xapp: RicDeleteXappModel):
        pass

    @final
    def wait_gnb_connection(self):
        return self.wait_gnb_connection_ric()

    @abstractmethod
    def wait_gnb_connection_ric(self):
        pass

    @final
    def get_connected_gnbs(self) -> List[tuple[str, str]]:
        return list(self.state.gnb_ids.items())

    @day2_function("/update", [HttpRequestType.PUT])
    def day2_update_ric(self, update_model: RICBlueCreateModel):
        """
        Update the RIC configuration
        Args:
            update_model: Same model as the create
        """
        if update_model.area_id != self.state.current_config.area_id:
            raise ValueError("Cannot change the area")
        self.update(update_model)

    @day2_function("/onboard_xapp", [HttpRequestType.PUT])
    def day2_onboard_xapp(self, xapp_data: RICOnboardXappModel):
        self.onboard_xapp(xapp_data)

    @day2_function("/run_xapp", [HttpRequestType.PUT])
    def day2_run_xapp(self, xapp: RICRunXappModel):
        self.run_xapp(xapp)

    @day2_function("/get_xapps", [HttpRequestType.GET])
    def day2_get_xapps(self) -> List[str]:
        return self.get_xapps()

    @day2_function("/delete_xapp", [HttpRequestType.PUT])
    def day2_delete_xapp(self, xapp: RicDeleteXappModel):
        self.delete_xapp(xapp)

    @day2_function("/connected_gnbs", [HttpRequestType.GET])
    def day2_connected_gnbs(self) -> List[tuple[str, str]]:
        self.get_connected_gnbs()
