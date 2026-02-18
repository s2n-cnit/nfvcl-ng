import copy
from abc import abstractmethod
from typing import Optional, TypeVar, Generic, final

from pydantic import Field

from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_models.blueprint_ng.g5.ran import RANBlueCreateModel, Split, GNBBlueCreateModel, GNBBlueCreateModelNetwork, CUBlueCreateModel, CUUPBlueCreateModel, CUCPBlueCreateModel, DUBlueCreateModel, RanInterfacesIps, RANBlueCreateModelGeneric, CUBlueCreateModelNetwork, CUCPBlueCreateModelNetwork, CUUPBlueCreateModelNetwork, DUBlueCreateModelNetwork
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import day2_function
from nfvcl_core_models.blueprints.blueprint import BlueprintNGState
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_core_models.network.network_models import PduModel
from nfvcl_core_models.network.network_models import PduType
from nfvcl_core_models.pdu.gnb import GNBPDUConfigure, GNBPDUDetach


class Generic5GRANBlueprintNGState(BlueprintNGState):
    current_config: Optional[RANBlueCreateModel] = Field(default=None)
    cu_blue_id: Optional[str] = Field(default=None)
    cu_cp_blue_id: Optional[str] = Field(default=None)
    cu_up_blue_id: Optional[str] = Field(default=None)
    du_blue_id: Optional[str] = Field(default=None)
    gnb_blue_id: Optional[str] = Field(default=None)
    gnb_model: Optional[GNBBlueCreateModel] = Field(default=None)
    cu_model: Optional[CUBlueCreateModel] = Field(default=None)
    cuup_model: Optional[CUUPBlueCreateModel] = Field(default=None)
    cucp_model: Optional[CUCPBlueCreateModel] = Field(default=None)
    du_model: Optional[DUBlueCreateModel] = Field(default=None)
    cu_ips: Optional[RanInterfacesIps] = Field(default=None)
    cucp_ips: Optional[RanInterfacesIps] = Field(default=None)
    cuup_ips: Optional[RanInterfacesIps] = Field(default=None)
    du_ips: Optional[RanInterfacesIps] = Field(default=None)
    gnb_ips: Optional[RanInterfacesIps] = Field(default=None)


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

    def extract_unique_net_names(self, model: RANBlueCreateModel) -> set:
        net_names = set()

        for endpoint in [model.networks.n2, model.networks.n3, model.networks.f1, model.networks.e1, model.networks.ru1, model.networks.ru2]:
            if endpoint:
                net_names.add(endpoint.net_name)

        return net_names

    def configuration_feasibility_check(self, config_model: RANBlueCreateModel):
        """
        Check if the config is feasible
        Args:
            config_model: Config model of which to check for feasibility
        """
        networks = self.extract_unique_net_names(config_model)
        ok, missing_nets = self.provider.check_networks(config_model.area_id, networks)
        if not ok:
            raise Exception(f"Missing nets {missing_nets}, from area {config_model.area_id}")

    @final
    def create(self, create_model: RANBlueCreateModel):
        super().create(create_model)
        self.state.current_config = copy.deepcopy(create_model)
        self.configuration_feasibility_check(create_model)
        base = RANBlueCreateModelGeneric(
            mcc=self.state.current_config.mcc,
            mnc=self.state.current_config.mnc,
            snssaiList=self.state.current_config.snssai_list,
            tac=self.state.current_config.tac,
            area_id=self.state.current_config.area_id,
            gnb_id=self.state.current_config.gnb_id
        )
        match self.state.current_config.split:
            case Split.CU_DU | Split.CP_UP_DU:
                match self.state.current_config.split:
                    case Split.CU_DU:
                        self.logger.info("Creating CU")
                        self.state.cu_model = CUBlueCreateModel(
                            **base.model_dump(),
                            amf=self.state.current_config.amf_host,
                            networks=CUBlueCreateModelNetwork(
                                n2=self.state.current_config.networks.n2,
                                n3=self.state.current_config.networks.n3,
                                f1=self.state.current_config.networks.f1,
                            ),
                        )
                        self.state.cu_blue_id = self.provider.create_blueprint(self.cu_blue_type, self.state.cu_model)
                        self.register_children(self.state.cu_blue_id)
                        self.logger.info("CU created")
                        self.state.cu_ips = self.provider.call_blueprint_function(self.state.cu_blue_id, "get_cu_interfaces_ip")

                    case _: #CUCP-CUUP
                        self.logger.info("Creating CUCP")
                        self.state.cucp_model = CUCPBlueCreateModel(
                            **base.model_dump(),
                            amf=self.state.current_config.amf_host,
                            f1Port="2152" if self.state.current_config.networks.n3.type == NetworkEndPointType.MULTUS and self.state.current_config.networks.f1.type == NetworkEndPointType.MULTUS else "2153",
                            networks=CUCPBlueCreateModelNetwork(
                                e1=self.state.current_config.networks.e1,
                                n2=self.state.current_config.networks.n2,
                                f1=self.state.current_config.networks.f1
                            )
                        )
                        self.state.cu_cp_blue_id = self.provider.create_blueprint(self.cucp_blue_type, self.state.cucp_model)
                        self.register_children(self.state.cu_cp_blue_id)
                        self.logger.info("CUCP created")
                        self.state.cucp_ips = self.provider.call_blueprint_function(self.state.cu_cp_blue_id, "get_cucp_interfaces_ip")

                        self.logger.info("Creating CUUP")
                        self.state.cuup_model = CUUPBlueCreateModel(
                            **base.model_dump(),
                            cuCpHost=self.state.cucp_ips.e1_cu_cp,
                            networks=CUUPBlueCreateModelNetwork(
                                e1=self.state.current_config.networks.e1,
                                n3=self.state.current_config.networks.n3,
                                f1=self.state.current_config.networks.f1
                            )
                        )
                        self.state.cu_up_blue_id = self.provider.create_blueprint(self.cuup_blue_type, self.state.cuup_model)
                        self.register_children(self.state.cu_up_blue_id)
                        self.logger.info("CUUP created")
                        self.state.cuup_ips = self.provider.call_blueprint_function(self.state.cu_up_blue_id, "get_cuup_interfaces_ip")

                self.logger.info("Creating DU")
                self.state.du_model = DUBlueCreateModel(
                    **base.model_dump(),
                    usrp=self.state.current_config.usrp,
                    cuHost=self.state.cu_ips.f1_cu if self.state.cu_ips else self.state.cucp_ips.f1_cu_cp,
                    f1Port="2152" if self.state.current_config.networks.n3.type == NetworkEndPointType.MULTUS and self.state.current_config.networks.f1.type == NetworkEndPointType.MULTUS else "2153",
                    networks=DUBlueCreateModelNetwork(
                        f1=self.state.current_config.networks.f1,
                        ru1=self.state.current_config.networks.ru1,
                        ru2=self.state.current_config.networks.ru2
                    )
                )
                self.state.du_blue_id = self.provider.create_blueprint(self.du_blue_type, self.state.du_model)
                self.register_children(self.state.du_blue_id)
                self.logger.info("DU created")
                self.state.du_ips = self.provider.call_blueprint_function(self.state.du_blue_id, "get_du_interfaces_ip")

            case _: #GNB
                self.logger.info("Creating GNB")
                self.state.gnb_model = GNBBlueCreateModel(
                    **base.model_dump(),
                    usrp=self.state.current_config.usrp,
                    amf=self.state.current_config.amf_host,
                    networks=GNBBlueCreateModelNetwork(
                        n2=self.state.current_config.networks.n2,
                        n3=self.state.current_config.networks.n3,
                        ru1=self.state.current_config.networks.ru1,
                        ru2=self.state.current_config.networks.ru2
                    )
                )
                self.state.gnb_blue_id = self.provider.create_blueprint(self.gnb_blue_type, self.state.gnb_model)
                self.register_children(self.state.gnb_blue_id)
                self.logger.info("GNB created")
                self.state.gnb_ips = self.provider.call_blueprint_function(self.state.gnb_blue_id, "get_gnb_interfaces_ip")

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

    def update_common_values(self, model: RANBlueCreateModelGeneric):
        model.mcc = self.state.current_config.mcc
        model.mnc = self.state.current_config.mnc
        model.snssai_list = self.state.current_config.snssai_list
        model.tac = self.state.current_config.tac
        model.area_id = self.state.current_config.area_id
        model.gnb_id = self.state.current_config.gnb_id
        model.additional_routes = self.state.current_config.additional_routes
        model.replica_count = self.state.current_config.replica_count

    @final
    def update(self, create_model: RANBlueCreateModel):
        self.state.current_config = copy.deepcopy(create_model)
        match self.state.current_config.split:
            case Split.CU_DU | Split.CP_UP_DU:
                match self.state.current_config.split:
                    case Split.CU_DU:
                        self.logger.info("Updating CU")
                        self.update_common_values(self.state.cu_model)
                        self.state.cu_model.amf = self.state.current_config.amf_host
                        self.provider.call_blueprint_function(self.state.cu_blue_id, "update", self.state.cu_model)
                        self.provider.call_blueprint_function(self.state.cu_blue_id, "restart_cu")

                    case _: #CUCP-CUUP
                        self.logger.info("Updating CUCP")
                        self.update_common_values(self.state.cucp_model)
                        self.state.cucp_model.amf = self.state.current_config.amf_host
                        self.provider.call_blueprint_function(self.state.cu_cp_blue_id, "update", self.state.cucp_model)
                        self.provider.call_blueprint_function(self.state.cu_cp_blue_id, "restart_cucp")

                        self.logger.info("Updating CUUP")
                        self.update_common_values(self.state.cuup_model)
                        self.provider.call_blueprint_function(self.state.cu_up_blue_id, "update", self.state.cuup_model)
                        self.provider.call_blueprint_function(self.state.cu_up_blue_id, "restart_cuup")

                self.logger.info("Updating DU")
                self.update_common_values(self.state.du_model)
                self.state.du_model.usrp = self.state.current_config.usrp
                self.provider.call_blueprint_function(self.state.du_blue_id, "update", self.state.du_model)
                self.provider.call_blueprint_function(self.state.du_blue_id, "restart_du")

            case _: #GNB
                self.logger.info("Updating GNB")
                self.update_common_values(self.state.gnb_model)
                self.state.gnb_model.usrp = self.state.current_config.usrp
                self.state.gnb_model.amf = self.state.current_config.amf_host
                self.provider.call_blueprint_function(self.state.gnb_blue_id, "update", self.state.gnb_model)
                self.provider.call_blueprint_function(self.state.gnb_blue_id, "restart_gnb", self.state.gnb_model)

        self.update_ran()

    @abstractmethod
    def update_ran(self):
        pass

    @day2_function("/configure_gnb", [HttpRequestType.POST])
    def configure_gnb(self, model: GNBPDUConfigure):
        self.state.current_config.replica_count = 1
        self.state.current_config.mcc = model.plmn[:3]
        self.state.current_config.mnc = model.plmn[3:]
        self.state.current_config.snssai_list = model.nssai
        self.state.current_config.tac = model.tac
        self.state.current_config.gnb_id = model.gnb_id
        self.state.current_config.additional_routes = model.additional_routes

        match self.state.current_config.split:
            case Split.CU_DU | Split.CP_UP_DU:
                match self.state.current_config.split:
                    case Split.CU_DU:
                        self.update_common_values(self.state.cu_model)
                        self.state.cu_model.amf = model.amf_ip
                        self.provider.call_blueprint_function(self.state.cu_blue_id, "update", self.state.cu_model)
                        self.provider.call_blueprint_function(self.state.cu_blue_id, "restart_cu")

                    case _: #CUCP-CUUP
                        self.update_common_values(self.state.cucp_model)
                        self.state.cucp_model.amf = model.amf_ip
                        self.provider.call_blueprint_function(self.state.cu_cp_blue_id, "update", self.state.cucp_model)
                        self.provider.call_blueprint_function(self.state.cu_cp_blue_id, "restart_cucp")

                        self.update_common_values(self.state.cuup_model)
                        self.provider.call_blueprint_function(self.state.cu_up_blue_id, "update", self.state.cuup_model)
                        self.provider.call_blueprint_function(self.state.cu_up_blue_id, "restart_cuup")

                self.update_common_values(self.state.du_model)
                self.provider.call_blueprint_function(self.state.du_blue_id, "update", self.state.du_model)
                self.provider.call_blueprint_function(self.state.du_blue_id, "restart_du")

            case _: #GNB
                self.update_common_values(self.state.gnb_model)
                self.state.gnb_model.amf = model.amf_ip
                self.provider.call_blueprint_function(self.state.gnb_blue_id, "update", self.state.gnb_model)
                self.provider.call_blueprint_function(self.state.gnb_blue_id, "restart_gnb")

    @day2_function("/detach_gnb", [HttpRequestType.POST])
    def detach_gnb(self, model: GNBPDUDetach):
        self.state.current_config.replica_count = 0
        match self.state.current_config.split:
            case Split.CU_DU | Split.CP_UP_DU:
                match self.state.current_config.split:
                    case Split.CU_DU:
                        self.update_common_values(self.state.cu_model)
                        self.provider.call_blueprint_function(self.state.cu_blue_id, "update", self.state.cu_model)

                    case _: #CUCP-CUUP
                        self.update_common_values(self.state.cucp_model)
                        self.provider.call_blueprint_function(self.state.cu_cp_blue_id, "update", self.state.cucp_model)

                        self.update_common_values(self.state.cuup_model)
                        self.provider.call_blueprint_function(self.state.cu_up_blue_id, "update", self.state.cuup_model)

                self.update_common_values(self.state.du_model)
                self.provider.call_blueprint_function(self.state.du_blue_id, "update", self.state.du_model)

            case _: #GNB
                self.update_common_values(self.state.gnb_model)
                self.provider.call_blueprint_function(self.state.gnb_blue_id, "update", self.state.gnb_model)

    def del_gnb_from_topology(self):
        try:
            self.provider.delete_pdu(f"{self.implementation_name}_GNB_{self.id}_{self.state.current_config.area_id}")
        except Exception as e:
            self.logger.warning(f"Error deleting PDU: {str(e)}")

    def destroy(self):
        self.del_gnb_from_topology()
        super().destroy()
