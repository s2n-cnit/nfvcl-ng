import copy
import time
from typing import Optional, Dict

from pydantic import Field

from nfvcl.blueprints_ng.modules.ueransim_k8s import ueransim_k8s_default_config
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl_core.providers.virtualization.virtualization_provider_openstack import DEFAULT_OPENSTACK_TIMEOUT
from nfvcl_core_models.blueprints.blueprint import BlueprintNGState, BlueprintNGException
from nfvcl_core_models.http_models import HttpRequestType
from nfvcl_core_models.network.network_models import PduModel, PduType
from nfvcl_core_models.pdu.gnb import GNBPDUConfigure
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.blueprint_ueransim_model import UeransimArea, UeransimUe
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointType
from nfvcl_models.blueprint_ng.g5.ue import UESim
from nfvcl_models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestInstance, UeransimBlueprintRequestAddUE, UeransimBlueprintRequestDelUE, UeransimBlueprintRequestAddSim, UeransimBlueprintRequestDelSim
from nfvcl_models.blueprint_ng.ueransim_k8s.ueransim_models import UeransimK8sModel, UeInstance, UEConfiguration, GNBConfiguration, Configmap, Volume

UERANSIM_BLUE_TYPE = "ueransim_k8s"


class UeransimBlueprintNGState(BlueprintNGState):
    current_config: Optional[UeransimBlueprintRequestInstance] = Field(default=None)
    ueransim_config_values: Optional[Dict[str, UeransimK8sModel]] = Field(default_factory=dict)
    ueransim_helm_chart: Optional[Dict[str, HelmChartResource]] = Field(default_factory=dict)


@blueprint_type(UERANSIM_BLUE_TYPE)
class UeransimK8sBlueprintNG(BlueprintNG[UeransimBlueprintNGState, UeransimBlueprintRequestInstance]):

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = UeransimBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: UeransimBlueprintRequestInstance):
        self.logger.info("Starting creation of UeransimK8s blueprint")
        self.state.current_config = copy.deepcopy(create_model)

        for area in create_model.areas:
            self.state.ueransim_config_values[str(area.id)] = copy.deepcopy(ueransim_k8s_default_config.ueransimk8s_default_config)
            self.spawn_gnb_ues(str(area.id))

    def spawn_gnb_ues(self, area_id: str):
        ran_config = self.state.ueransim_config_values[area_id]
        self.state.ueransim_helm_chart[area_id] = HelmChartResource(
            area=int(area_id),
            name=f"ueransimk8s-{area_id}",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/ueransimk8s-2.0.17.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.ueransim_helm_chart[area_id])

        if self.state.current_config.config.network_endpoints.n2.type == NetworkEndPointType.MULTUS:
            net_n2 = self.provider.reserve_k8s_multus_ip(self.state.current_config.areas[0].id, self.state.current_config.config.network_endpoints.n2.net_name)
            ran_config.global_.n2network.set_multus(True, net_n2)
            ran_config.gnb.n2if.ipAddress = net_n2.ip_address.exploded
            ran_config.gnb.amf.service.ngap.enabled = False

        if self.state.current_config.config.network_endpoints.n3.type == NetworkEndPointType.MULTUS:
            net_n3 = self.provider.reserve_k8s_multus_ip(self.state.current_config.areas[0].id, self.state.current_config.config.network_endpoints.n3.net_name)
            ran_config.global_.n3network.set_multus(True, net_n3)
            ran_config.gnb.n3if.ipAddress = net_n3.ip_address.exploded

        self.update_ueransim_values(area_id)

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.ueransim_helm_chart[area_id],
            ran_config.model_dump(exclude_none=True, by_alias=True)
        )
        self.add_gnb_to_topology(int(area_id))

    def update_ueransim_values(self, area_id: str):
        area: UeransimArea = next((obj for obj in self.state.current_config.areas if obj.id == int(area_id)), None)
        if area:
            self.state.ueransim_config_values[area_id].gnb.service.name = f"gnb-{self.id}-service{area_id}".lower()
            self.state.ueransim_config_values[area_id].ue.instances.clear()
            for ue in area.ues:
                for sim in ue.sims:
                    new_ue = UeInstance(
                        name=f'ue{ue.id}-{sim.imsi}',
                        configmap=Configmap(
                            name=f'ue{ue.id}-area-{area_id}-{sim.imsi}-configmap'
                        ),
                        volume=Volume(
                            name=f'ue{ue.id}-area-{area_id}-{sim.imsi}-volume'
                        ),
                        configuration=UEConfiguration(
                            supi=f'imsi-{sim.imsi}',
                            mcc=sim.plmn[0:3],
                            mnc=sim.plmn[-2:],
                            key=sim.key,
                            op=sim.op,
                            opType=sim.opType,
                            amf=sim.amf,
                            sessions=sim.sessions,
                            configured_nssai=sim.configured_nssai,
                            default_nssai=sim.default_nssai
                        )
                    )
                    self.state.ueransim_config_values[area_id].ue.instances.append(new_ue)
        else:
            raise Exception(f"Area {area_id} not found")

    def update_ueransim(self, area_id: str):
        self.update_ueransim_values(area_id)
        self.provider.update_values_helm_chart(
            self.state.ueransim_helm_chart[area_id],
            self.state.ueransim_config_values[area_id].model_dump(exclude_none=True, by_alias=True)
        )


    def add_gnb_to_topology(self, area_id: int):
        self.provider.add_pdu(PduModel(
            name=f"UERANSIM_GNB_{self.id}_{area_id}",
            area=area_id,
            type=PduType.GNB,
            instance_type="UERANSIM",
            config={"blue_id": self.id}
        ))

    def del_gnb_from_topology(self, area_id: int):
        try:
            self.provider.delete_pdu(f"UERANSIM_GNB_{self.id}_{area_id}")
        except Exception as e:
            self.logger.warning(f"Error deleting PDU: {str(e)}")

    def destroy(self):
        for area in self.state.current_config.areas:
            self.del_gnb_from_topology(area.id)
        super().destroy()

    def _create_ue(self, area_id: str, ue: UeransimUe):
        area: UeransimArea = next((obj for obj in self.state.current_config.areas if obj.id == int(area_id)), None)
        if area:
            if ue not in area.ues:
                area.ues.append(ue)
                self.update_ueransim(area_id)
            else:
                raise BlueprintNGException(f"Ue already present in {area_id}")
        else:
            raise BlueprintNGException(f"Gnb in area {area_id} not found")

    def _delete_ue(self, area_id: str, ue_id: int):
        area: UeransimArea = next((obj for obj in self.state.current_config.areas if obj.id == int(area_id)), None)
        if area:
            ue: UeransimUe = next((obj for obj in area.ues if obj.id == ue_id), None)
            if ue:
                area.ues.remove(ue)
                self.update_ueransim(area_id)
            else:
                raise BlueprintNGException(f"Ue {ue_id} not found in area {area_id}")
        else:
            raise BlueprintNGException(f"Area {area_id} not found")

    def _add_sim(self, area_id: str, ue_id: int, new_sim: UESim):
        area: UeransimArea = next((obj for obj in self.state.current_config.areas if obj.id == int(area_id)), None)
        if area:
            ue: UeransimUe = next((obj for obj in area.ues if obj.id == ue_id), None)
            if ue and new_sim not in ue.sims:
                ue.sims.append(new_sim)
                self.update_ueransim(area_id)
            else:
                raise BlueprintNGException(f"Ue {ue_id} not found or sim {new_sim.imsi} already present")
        else:
            raise BlueprintNGException(f"Area {area_id} not found")

    def _del_sim(self, area_id: str, ue_id: int, imsi: str):
        area: UeransimArea = next((obj for obj in self.state.current_config.areas if obj.id == int(area_id)), None)
        if area:
            ue: UeransimUe = next((obj for obj in area.ues if obj.id == ue_id), None)
            if ue:
                sim: UESim = next((obj for obj in ue.sims if obj.imsi == imsi), None)
                if sim:
                    ue.sims.remove(sim)
                    self.update_ueransim(area_id)
                else:
                    raise BlueprintNGException(f"Sim {imsi} not found for ue {ue_id}")
            else:
                raise BlueprintNGException(f"Ue {ue_id} not found")
        else:
            raise BlueprintNGException(f"Area {area_id} not found")

    def restart_ran(self, area_id: str):
        gnb_deployment_name = f"ueransimk8s-{area_id}-gnb"
        self.logger.info(f"Restarting gnb area {area_id}")
        self.provider.restart_deployment(self.state.ueransim_helm_chart[area_id], gnb_deployment_name)
        self.logger.info("Restarting ues area {area_id}")
        for ue in self.state.ueransim_config_values[area_id].ue.instances:
            self.provider.restart_deployment(self.state.ueransim_helm_chart[area_id], f"ueransimk8s-{area_id}-{ue.name}")

    @day2_function("/configure_gnb", [HttpRequestType.POST])
    def configure_gnb(self, model: GNBPDUConfigure):
        area_id = str(model.area)
        self.state.ueransim_config_values[area_id].gnb.amf.n2if.ipAddress = model.amf_ip
        self.state.ueransim_config_values[area_id].gnb.configuration = GNBConfiguration(
            mcc=model.plmn[0:3],
            mnc=model.plmn[-2:],
            nci=f'0x{model.tac}',
            idLength=32,
            tac=model.tac,
            slices=model.nssai
        )
        additional_route_list = []
        for route in model.additional_routes:
            tmp = route.as_linux_replace_command()
            if tmp not in self.state.ueransim_config_values[area_id].gnb.additional_routes:
                additional_route_list.append(tmp)
        self.state.ueransim_config_values[area_id].gnb.additional_routes = additional_route_list
        self.update_ueransim(area_id)
        self.restart_ran(area_id)

    @day2_function("/add_ue", [HttpRequestType.POST])
    def add_ue(self, model: UeransimBlueprintRequestAddUE):
        self._create_ue(model.area_id, model.ue)

    @day2_function("/del_ue", [HttpRequestType.DELETE])
    def del_ue(self, model: UeransimBlueprintRequestDelUE):
        self._delete_ue(model.area_id, model.ue_id)

    @day2_function("/add_sim", [HttpRequestType.POST])
    def add_sim(self, model: UeransimBlueprintRequestAddSim):
        self._add_sim(model.area_id, model.ue_id, model.sim)

    @day2_function("/del_sim", [HttpRequestType.DELETE])
    def del_sim(self, model: UeransimBlueprintRequestDelSim):
        self._del_sim(model.area_id, model.ue_id, model.imsi)
