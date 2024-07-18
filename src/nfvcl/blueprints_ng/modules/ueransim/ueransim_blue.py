from __future__ import annotations

from typing import List, Optional, Dict

from pydantic import Field

from nfvcl.blueprints_ng.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState, BlueprintNGException
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type, day2_function
from nfvcl.blueprints_ng.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration, \
    NetResource
from nfvcl.blueprints_ng.utils import rel_path
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestConfigureGNB, \
    UeransimBlueprintRequestInstance, UeransimBlueprintRequestAddDelGNB, UeransimBlueprintRequestAddUE, \
    UeransimBlueprintRequestDelUE, UeransimBlueprintRequestAddSim, UeransimBlueprintRequestDelSim, GNBN3Info
from nfvcl.models.http_models import HttpRequestType
from nfvcl.models.network import PduModel
from nfvcl.models.ueransim.blueprint_ueransim_model import UeransimSim, UeransimUe
from nfvcl.topology.topology import build_topology

UERANSIM_BLUE_TYPE = "ueransim"


class BlueUeransimUe(NFVCLBaseModel):
    ue_id: str = Field()
    vm_ue: Optional[VmResource] = Field(default=None)
    vm_ue_configurator: Optional[UeransimUEConfigurator] = Field(default=None)


class BlueUeransimArea(NFVCLBaseModel):
    vm_gnb: Optional[VmResource] = Field(default=None)
    vm_gnb_configurator: Optional[UeransimGNBConfigurator] = Field(default=None)
    ues: List[BlueUeransimUe] = Field(default_factory=list)
    radio_net: Optional[NetResource] = Field(default=None)


class UeransimBlueprintNGState(BlueprintNGState):
    areas: Dict[str, BlueUeransimArea] = Field(default_factory=dict)


class UeransimGNBConfigurator(VmResourceAnsibleConfiguration):
    configuration: UeransimBlueprintRequestConfigureGNB = Field()
    radio_addr: str = Field()
    ngap_addr: str = Field()
    gtp_addr: str = Field()
    n3_nic_name: str = Field()

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook UeransimGNBConfigurator")
        ansible_builder.add_template_task(rel_path("config/gnb_conf_file.jinja2"), "/opt/UERANSIM/gnb.conf")
        ansible_builder.set_vars_from_fields(self.configuration)
        ansible_builder.set_var("radio_addr", self.radio_addr)
        ansible_builder.set_var("ngap_addr", self.ngap_addr)
        ansible_builder.set_var("gtp_addr", self.gtp_addr)

        ansible_builder.add_template_task(rel_path("config/config_network.sh.jinja2"), "/opt/config_network.sh")
        ansible_builder.add_template_task(rel_path("config/config-network.service.jinja2"), "/etc/systemd/system/config-network.service")
        ansible_builder.set_var("n3_if", self.n3_nic_name)
        ansible_builder.add_shell_task("systemctl daemon-reload")
        ansible_builder.add_service_task("config-network", ServiceState.STARTED, True)

        ansible_builder.add_service_task("ueransim-gnb", ServiceState.RESTARTED, True)

        return ansible_builder.build()


class UeransimUEConfigurator(VmResourceAnsibleConfiguration):
    sims: List[UeransimSim] = Field()
    gnbSearchList: List[str] = Field()
    sims_to_delete: List[UeransimSim] = Field(default_factory=list)

    def update_sims(self, new_sims: List[UeransimSim]):
        self.sims_to_delete = list(set(self.sims) - set(new_sims))
        self.sims = new_sims

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder(f"Playbook UeransimUEConfigurator")

        for sim in self.sims_to_delete:
            ue_sim_config_path = f"/opt/UERANSIM/ue-sim-{sim.imsi}.conf"
            ue_sim_service_path = f"/etc/systemd/system/ueransim-ue-sim-{sim.imsi}.service"
            ansible_builder.add_service_task(
                service_name=f"ueransim-ue-sim-{sim.imsi}",
                service_state=ServiceState.STOPPED,
                enabled=False
            )
            ansible_builder.add_shell_task(command=f"rm {ue_sim_config_path} {ue_sim_service_path}")
        self.sims_to_delete.clear()

        for sim in self.sims:
            ue_sim_config_path = f"/opt/UERANSIM/ue-sim-{sim.imsi}.conf"
            ansible_builder.add_template_task(rel_path("config/ue_conf_file.jinja2"), ue_sim_config_path,
                                              {"sim": sim, "gnbSearchList": self.gnbSearchList})

            # Create a new service to start the UE with this SIM
            ue_sim_service_path = f"/etc/systemd/system/ueransim-ue-sim-{sim.imsi}.service"
            ansible_builder.add_copy_task(
                "/etc/systemd/system/ueransim-ue.service",
                ue_sim_service_path,
                remote_src=True
            )
            ansible_builder.add_replace_task(ue_sim_service_path, "/opt/UERANSIM/ue.conf", ue_sim_config_path)
            ansible_builder.add_replace_task(ue_sim_service_path, "UERANSIM UE", f"UERANSIM UE SIM {sim.imsi}")

            ansible_builder.add_shell_task("systemctl daemon-reload")
            ansible_builder.add_service_task(f"ueransim-ue-sim-{sim.imsi}", ServiceState.RESTARTED, True)

        return ansible_builder.build()


@blueprint_type(UERANSIM_BLUE_TYPE)
class UeransimBlueprintNG(BlueprintNG[UeransimBlueprintNGState, UeransimBlueprintRequestInstance]):
    # RADIO_NET_CIDR = '10.168.0.0/16'
    # RADIO_NET_CIDR_START = '10.168.0.2'
    # RADIO_NET_CIDR_END = '10.168.255.253'

    ueransim_image = VmResourceImage(name="ueransim-v3.2.6-dev-2", url="https://images.tnt-lab.unige.it/ueransim/ueransim-v3.2.6-dev-2-ubuntu2204.qcow2")
    ueransim_flavor = VmResourceFlavor(vcpu_count='2', memory_mb='4096', storage_gb='10')

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = UeransimBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: UeransimBlueprintRequestInstance):
        super().create(create_model)
        self.logger.info("Starting creation of UERANSIM blueprint")
        for area in create_model.areas:
            self._create_gnb(str(area.id))
            for ue in area.ues:
                self._create_ue(str(area.id), ue)

    def destroy(self):
        for area in self.state.areas.keys():
            self.del_gnb_from_topology(int(area))
        super().destroy()

    def add_gnb_to_topology(self, area_id: int):
        name = f"UERANSIM_GNB_{self.id}_{area_id}"
        build_topology().add_pdu(PduModel(
            name=name,
            area=area_id,
            type="UERANSIM",
            user="",
            passwd="",
            implementation="nfvcl.blueprints_ng.pdu_configurators.ueransim_pdu_configurator.UERANSIMPDUConfigurator",  # TODO this should be dynamic
            config={"blue_id": self.id},
            interface=[]
        ))

    def del_gnb_from_topology(self, area_id: int):
        build_topology().del_pdu(f"UERANSIM_GNB_{self.id}_{area_id}")

    def _create_gnb(self, area_id: str):
        if area_id not in self.state.areas:
            radio_network_name = f"radio_{self.id}_{area_id}"
            network = NetResource(area=int(area_id), name=radio_network_name, cidr=f"10.168.{area_id}.0/24")
            self.register_resource(network)
            self.provider.create_net(network)

            vm_gnb = VmResource(
                area=int(area_id),
                name=f"{self.id}_{area_id}_GNB",
                image=self.ueransim_image,
                flavor=self.ueransim_flavor,
                username="ubuntu",
                password="ubuntu",
                management_network=self.create_config.config.network_endpoints.mgt,
                additional_networks=[self.create_config.config.network_endpoints.n2, self.create_config.config.network_endpoints.n3, radio_network_name],
                require_port_security_disabled=True
            )

            self.register_resource(vm_gnb)
            self.provider.create_vm(vm_gnb)
            self.state.areas[area_id] = BlueUeransimArea(vm_gnb=vm_gnb, ues=[], radio_net=network)
            self.add_gnb_to_topology(int(area_id))
        else:
            raise BlueprintNGException(f"GnB already exists in area {area_id}")

    def _create_ue(self, area_id: str, ue: UeransimUe):
        if area_id in self.state.areas:
            blue_ueransim_area = self.state.areas[area_id]
            radio_network_name = f"radio_{self.id}_{area_id}"
            vm_ue = VmResource(
                area=int(area_id),
                name=f"{self.id}_{area_id}_UE_{ue.id}",
                image=self.ueransim_image,
                flavor=self.ueransim_flavor,
                username="ubuntu",
                password="ubuntu",
                management_network=self.create_config.config.network_endpoints.mgt,
                additional_networks=[radio_network_name]
            )
            self.register_resource(vm_ue)

            self.provider.create_vm(vm_ue)

            vm_ue_configurator = UeransimUEConfigurator(
                vm_resource=vm_ue,
                sims=[],
                gnbSearchList=[blue_ueransim_area.vm_gnb.network_interfaces[radio_network_name][0].fixed.ip]
            )
            for sim in ue.sims:
                vm_ue_configurator.sims.append(sim)

            self.register_resource(vm_ue_configurator)
            self.provider.configure_vm(vm_ue_configurator)
            blue_ueransim_area.ues.append(BlueUeransimUe(vm_ue=vm_ue, vm_ue_configurator=vm_ue_configurator, ue_id=str(ue.id)))

            self.state.areas[area_id] = blue_ueransim_area
        else:
            raise BlueprintNGException(f"Gnb in area {area_id} not found")

    def _delete_gnb(self, area_id: str):
        self.logger.info(f"Trying to delete GnB in area {area_id}")
        if area_id in self.state.areas:
            for ue in self.state.areas[area_id].ues:
                self.provider.destroy_vm(ue.vm_ue)
                self.deregister_resource(ue.vm_ue)
                self.deregister_resource(ue.vm_ue_configurator)

            self.provider.destroy_vm(self.state.areas[area_id].vm_gnb)
            self.deregister_resource(self.state.areas[area_id].vm_gnb)
            if self.state.areas[area_id].vm_gnb_configurator:
                self.deregister_resource(self.state.areas[area_id].vm_gnb_configurator)
            del self.state.areas[area_id]
            self.del_gnb_from_topology(int(area_id))
        else:
            raise BlueprintNGException(f"No Gnb found in area {area_id}")

    def _delete_ue(self, area_id: str, ue_id: int):
        self.logger.info(f"Trying to delete UE {ue_id} in area {area_id}")
        if area_id in self.state.areas:
            temp = self.state.areas[area_id].ues.copy()
            for ue in temp:
                if ue.ue_id == str(ue_id):
                    self.provider.destroy_vm(ue.vm_ue)
                    self.deregister_resource(ue.vm_ue)
                    self.deregister_resource(ue.vm_ue_configurator)
                    self.state.areas[area_id].ues.remove(ue)
                    self.logger.info(f"UE {ue_id} deleted")
                else:
                    raise BlueprintNGException(f"No UE found in area {area_id} with id {ue_id}")
        else:
            raise BlueprintNGException(f"No Gnb found in area {area_id}")

    def _add_sim(self, area_id: str, ue_id: int, new_sim: UeransimSim):
        self.logger.info(f"Trying to add Sim with imsi {new_sim.imsi}, in area {area_id}, ue {ue_id}")
        for ue in self.state.areas[area_id].ues:
            if ue.ue_id == str(ue_id):
                for sim in ue.vm_ue_configurator.sims:
                    if sim.imsi == new_sim.imsi:
                        raise BlueprintNGException(f"Sim {new_sim.imsi} already exists")
                ue.vm_ue_configurator.sims.append(new_sim)
                self.provider.configure_vm(ue.vm_ue_configurator)
                self.logger.info(f"Sim with imsi {new_sim.imsi} added")

    def _del_sim(self, area_id: str, ue_id: int, imsi: str):
        self.logger.info(f"Trying to delete Sim with imsi {imsi}, from area {area_id}, ue {ue_id}")
        for ue in self.state.areas[area_id].ues:
            if ue.ue_id == str(ue_id):
                temp = ue.vm_ue_configurator.sims.copy()
                for sim in temp:
                    if sim.imsi == imsi:
                        ue.vm_ue_configurator.sims_to_delete.append(sim)
                        ue.vm_ue_configurator.sims.remove(sim)
                        self.provider.configure_vm(ue.vm_ue_configurator)
                        self.logger.info(f"Sim with imsi {imsi} deleted")
                        return
                raise BlueprintNGException(f"Sim with imsi {imsi} does not exist")

    @day2_function("/add_gnb", [HttpRequestType.POST])
    def add_gnb(self, model: UeransimBlueprintRequestAddDelGNB):
        self._create_gnb(model.area_id)

    @day2_function("/configure_gnb", [HttpRequestType.POST])
    def configure_gnb(self, model: UeransimBlueprintRequestConfigureGNB):
        area = self.state.areas[str(model.area)]
        area.vm_gnb_configurator = UeransimGNBConfigurator(
            vm_resource=area.vm_gnb,
            configuration=model,
            radio_addr=area.vm_gnb.network_interfaces[area.radio_net.name][0].fixed.ip,
            ngap_addr=area.vm_gnb.network_interfaces[self.create_config.config.network_endpoints.n2][0].fixed.ip,
            gtp_addr=area.vm_gnb.network_interfaces[self.create_config.config.network_endpoints.n3][0].fixed.ip,
            n3_nic_name=area.vm_gnb.network_interfaces[self.create_config.config.network_endpoints.n3][0].fixed.interface_name
        )

        self.register_resource(area.vm_gnb_configurator)
        self.provider.configure_vm(area.vm_gnb_configurator)

    @day2_function("/del_gnb", [HttpRequestType.DELETE])
    def del_gnb(self, model: UeransimBlueprintRequestAddDelGNB):
        self._delete_gnb(model.area_id)

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

    def get_n3_info(self, area_id: int) -> GNBN3Info:
        return GNBN3Info(
            ip=self.state.areas[str(area_id)].vm_gnb.network_interfaces[self.create_config.config.network_endpoints.n3][0].fixed.ip,
            mac=self.state.areas[str(area_id)].vm_gnb.network_interfaces[self.create_config.config.network_endpoints.n3][0].fixed.mac
        )
