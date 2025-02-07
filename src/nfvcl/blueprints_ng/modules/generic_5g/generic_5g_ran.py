import copy
from abc import abstractmethod
from typing import Optional, TypeVar, Generic, final

from pydantic import Field

from nfvcl.models.blueprint_ng.g5.ran import RANBlueCreateModel, Split, GNBBlueCreateModel, GNBBlueCreateModelNetwork
from nfvcl_core.blueprints import BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import day2_function
from nfvcl_core.managers import get_blueprint_manager
from nfvcl_core.models.blueprints import BlueprintNGState
from nfvcl_core.models.http_models import HttpRequestType
from nfvcl_core.models.network import PduModel
from nfvcl_core.models.network.network_models import PduType
from nfvcl_core.models.pdu.gnb import GNBPDUConfigure


class Generic5GRANBlueprintNGState(BlueprintNGState):
    current_config: Optional[RANBlueCreateModel] = Field(default=None)
    cu_id: Optional[str] = Field(default=None)
    cu_cp_id: Optional[str] = Field(default=None)
    cu_up_id: Optional[str] = Field(default=None)
    du_id: Optional[str] = Field(default=None)
    gnb_id: Optional[str] = Field(default=None)
    gnb_model: Optional[GNBBlueCreateModel] = Field(default=None)


StateTypeVar5GRAN = TypeVar("StateTypeVar5GRAN", bound=Generic5GRANBlueprintNGState)
CreateConfigTypeVar5GRAN = TypeVar("CreateConfigTypeVar5GRAN")


class Generic5GRANBlueprintNG(BlueprintNG[Generic5GRANBlueprintNGState, RANBlueCreateModel], Generic[StateTypeVar5GRAN, CreateConfigTypeVar5GRAN]):
    gnb_blue_type = None
    cu_blue_type = None
    cucp_blue_type = None
    cuup_blue_type = None
    du_blue_type = None
    implementation_name = None

    def __init__(self, blueprint_id: str, state_type: type[Generic5GRANBlueprintNGState] = StateTypeVar5GRAN):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GRAN:
        return super().state

    @final
    def create(self, create_model: RANBlueCreateModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        match self.state.current_config.split:
            case Split.GNB:
                self.state.gnb_model = GNBBlueCreateModel(
                    mcc=self.state.current_config.mcc,
                    mnc=self.state.current_config.mnc,
                    sst=self.state.current_config.sst,
                    sd=self.state.current_config.sd,
                    tac=self.state.current_config.tac,
                    area_id=self.state.current_config.area_id,
                    networks=GNBBlueCreateModelNetwork(
                        n2=self.state.current_config.networks.n2,
                        n3=self.state.current_config.networks.n3,
                        ru1=self.state.current_config.networks.ru1,
                        ru2=self.state.current_config.networks.ru2
                    ),
                    usrp=self.state.current_config.usrp
                )
                self.state.gnb_id = self.provider.create_blueprint(self.gnb_blue_type, self.state.gnb_model)
                self.register_children(self.state.gnb_id)
            case Split.CU_DU:
                pass
            case _:
                pass

        self.create_ran()
        self.provider.add_pdu(PduModel(
            name=f"{self.implementation_name}_GNB_{self.id}_{self.state.current_config.area_id}",
            area=self.state.current_config.area_id,
            type=PduType.GNB,
            instance_type="GENERIC_RAN",
            config={"blue_id": self.id}
        ))

    @abstractmethod
    def create_ran(self):
        pass

    @final
    def update(self, create_model: RANBlueCreateModel):
        self.state.current_config = copy.deepcopy(create_model)
        match self.state.current_config.split:
            case Split.GNB:
                self.state.gnb_model.mcc = self.state.current_config.mcc
                self.state.gnb_model.mnc = self.state.current_config.mnc
                self.state.gnb_model.sst = self.state.current_config.sst
                self.state.gnb_model.sd = self.state.current_config.sd
                self.state.gnb_model.tac = self.state.current_config.tac
                self.state.gnb_model.area_id = self.state.current_config.area_id
                self.state.gnb_model.usrp = self.state.current_config.usrp
                self.state.gnb_model.amf = self.state.current_config.amf

                self.provider.call_blueprint_function(self.state.gnb_id, "update", self.state.gnb_model)
            case Split.CU_DU:
                pass
            case _:
                pass
        self.update_ran()

    @abstractmethod
    def update_ran(self):
        pass

    @day2_function("/configure_gnb", [HttpRequestType.POST])
    def configure_gnb(self, model: GNBPDUConfigure):
        self.state.current_config.mcc = model.plmn[:3]
        self.state.current_config.mnc = model.plmn[3:]
        self.state.current_config.sst = str(model.nssai[0].sst)
        self.state.current_config.sd = str(model.nssai[0].sd)
        self.state.current_config.tac = str(model.tac)
        self.state.current_config.amf = model.amf_ip

        match self.state.current_config.split:
            case Split.GNB:
                self.state.gnb_model.mcc = self.state.current_config.mcc
                self.state.gnb_model.mnc = self.state.current_config.mnc
                self.state.gnb_model.sst = self.state.current_config.sst
                self.state.gnb_model.sd = self.state.current_config.sd
                self.state.gnb_model.tac = self.state.current_config.tac
                self.state.gnb_model.amf = self.state.current_config.amf

                self.provider.call_blueprint_function(self.state.gnb_id, "update", self.state.gnb_model)
            case Split.CU_DU:
                pass
            case _:
                pass

    def del_gnb_from_topology(self):
        try:
            self.provider.delete_pdu(f"{self.implementation_name}_GNB_{self.id}_{self.state.current_config.area_id}")
        except Exception as e:
            self.logger.warning(f"Error deleting PDU: {str(e)}")

    def destroy(self):
        self.del_gnb_from_topology()
        super().destroy()
