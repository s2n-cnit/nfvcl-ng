from typing import List, Optional, Dict

from pydantic import Field

from nfvcl_models.blueprint_ng.g5.ue import UESim
from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG, BlueprintNGState, BlueprintNGException
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl_core_models.linux.ip import Route
from nfvcl_core_models.network.network_models import PduType, PduModel
from nfvcl_core_models.pdu.gnb import GNBPDUConfigure, GNBPDUDetach
from nfvcl_core_models.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_models.blueprint_ng.g5.packetrusher import (
    PacketRusherBlueprintRequestInstance,
    PacketRusherBlueprintRequestAddDelArea,
    PacketRusherBlueprintRequestAddSim,
    PacketRusherBlueprintRequestDelSim,
)
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_common.utils.blue_utils import rel_path

PACKETRUSHER_BLUE_TYPE = "packetrusher"

# Base SCTP source port for the gNB control interface; incremented per SIM instance
# to avoid port conflicts when multiple PacketRusher processes run on the same VM.
BASE_CONTROLIF_PORT = 9487


class BluePacketRusherArea(NFVCLBaseModel):
    vm: Optional[VmResource] = Field(default=None)
    vm_configurator: Optional['PacketRusherConfigurator'] = Field(default=None)
    # SIMs queued before configure_gnb is called (AMF IP not yet known)
    pending_sims: List[UESim] = Field(default_factory=list)


class PacketRusherBlueprintNGState(BlueprintNGState):
    areas: Dict[str, BluePacketRusherArea] = Field(default_factory=dict)


class PacketRusherConfigurator(VmResourceAnsibleConfiguration):
    configuration: GNBPDUConfigure = Field()
    n2_addr: str = Field()
    n3_addr: str = Field()
    n3_nic_name: str = Field()
    sims: List[UESim] = Field(default_factory=list)
    sims_to_delete: List[UESim] = Field(default_factory=list)
    additional_routes: Optional[List[Route]] = Field(default_factory=list)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook PacketRusherConfigurator")

        # Network setup: disable hardware offload on N3, apply extra routes
        if self.additional_routes:
            additional_routes_str = [r.as_linux_replace_command() for r in self.additional_routes]
            ansible_builder.set_var("additional_routes", additional_routes_str)
        ansible_builder.set_var("n3_if", self.n3_nic_name)
        ansible_builder.add_template_task(rel_path("config/config_network.sh.jinja2"), "/opt/config_network.sh")
        ansible_builder.add_template_task(rel_path("config/config-network.service.jinja2"), "/etc/systemd/system/config-network.service")
        ansible_builder.add_shell_task("systemctl daemon-reload")
        ansible_builder.add_service_task("config-network", ServiceState.RESTARTED, True)

        # Stop and clean up removed SIMs
        had_deletions = len(self.sims_to_delete) > 0
        for sim in self.sims_to_delete:
            service_name = f"packetrusher-ue-{sim.imsi}"
            config_path = f"/opt/PacketRusher/config-{sim.imsi}.yml"
            service_path = f"/etc/systemd/system/{service_name}.service"
            ansible_builder.add_service_task(service_name, ServiceState.STOPPED, False)
            ansible_builder.add_shell_task(f"rm -f {config_path} {service_path}")
        self.sims_to_delete.clear()
        if had_deletions:
            ansible_builder.add_shell_task("systemctl daemon-reload")

        # Extract gNB parameters from GNBPDUConfigure
        mcc = self.configuration.plmn[:3]
        mnc = self.configuration.plmn[3:]
        tac = format(self.configuration.tac, '06X')
        gnb_id_base = self.configuration.gnb_id
        amf_ip = self.configuration.amf_ip
        amf_port = self.configuration.amf_port

        if self.configuration.nssai:
            first_slice = self.configuration.nssai[0]
            gnb_sst = format(int(first_slice.sst), '02X')
            gnb_sd = first_slice.sd  # already a 6-char uppercase hex string (SDType)
        else:
            gnb_sst = "01"
            gnb_sd = "000001"

        # Configure each SIM: write config file and install per-SIM systemd service
        for idx, sim in enumerate(self.sims):
            msin = sim.imsi[len(sim.plmn):]
            sim_mcc = sim.plmn[:3]
            sim_mnc = sim.plmn[3:]

            dnn = "internet"
            sim_sst = gnb_sst
            sim_sd = gnb_sd
            if sim.sessions:
                dnn = sim.sessions[0].dnn
                s = sim.sessions[0].slice
                sim_sst = format(int(s.sst), '02X')
                sim_sd = s.sd  # SDType: already a 6-char uppercase hex string

            amf_val = format(sim.amf, '04X') if sim.amf else "8000"
            gnb_id = format(gnb_id_base + idx, '06X')
            controlif_port = BASE_CONTROLIF_PORT + idx

            config_path = f"/opt/PacketRusher/config-{sim.imsi}.yml"
            service_name = f"packetrusher-ue-{sim.imsi}"
            service_path = f"/etc/systemd/system/{service_name}.service"

            template_vars = {
                "n2_addr": self.n2_addr,
                "n3_addr": self.n3_addr,
                "mcc": mcc,
                "mnc": mnc,
                "tac": tac,
                "gnb_id": gnb_id,
                "controlif_port": controlif_port,
                "gnb_sst": gnb_sst,
                "gnb_sd": gnb_sd,
                "sim_mcc": sim_mcc,
                "sim_mnc": sim_mnc,
                "msin": msin,
                "ue_key": sim.key,
                "ue_opc": sim.op,
                "ue_amf": amf_val,
                "dnn": dnn,
                "sim_sst": sim_sst,
                "sim_sd": sim_sd,
                "amf_ip": amf_ip,
                "amf_port": amf_port,
                "imsi": sim.imsi,
                "config_path": config_path,
            }

            ansible_builder.add_template_task(rel_path("config/config_yml.jinja2"), config_path, template_vars)
            ansible_builder.add_template_task(rel_path("config/packetrusher-ue.service.jinja2"), service_path, template_vars)
            ansible_builder.add_shell_task("systemctl daemon-reload")
            ansible_builder.add_service_task(service_name, ServiceState.RESTARTED, True)

        return ansible_builder.build()


class PacketRusherConfiguratorDetach(VmResourceAnsibleConfiguration):
    sims: List[UESim] = Field(default_factory=list)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook PacketRusherConfiguratorDetach")
        for sim in self.sims:
            ansible_builder.add_service_task(f"packetrusher-ue-{sim.imsi}", ServiceState.STOPPED, False)
        return ansible_builder.build()


@blueprint_type(PACKETRUSHER_BLUE_TYPE)
class PacketRusherBlueprintNG(BlueprintNG[PacketRusherBlueprintNGState, PacketRusherBlueprintRequestInstance]):
    packetrusher_image = VmResourceImage(
        name="packetrusher-v.0.0.1",
        url="https://images.tnt-lab.unige.it/packetrusher/packetrusher-v.0.0.1-ubuntu2404.qcow2"
    )
    packetrusher_flavor = VmResourceFlavor(vcpu_count='2', memory_mb='4096', storage_gb='10')

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = PacketRusherBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: PacketRusherBlueprintRequestInstance):
        super().create(create_model)
        self.logger.info("Starting creation of PacketRusher blueprint")
        for area in create_model.areas:
            self._create_area(str(area.id), area.sims)

    def destroy(self):
        for area in self.state.areas.keys():
            self.del_gnb_from_topology(int(area))
        super().destroy()

    def add_gnb_to_topology(self, area_id: int):
        self.provider.add_pdu(PduModel(
            name=f"PACKETRUSHER_GNB_{self.id}_{area_id}",
            area=area_id,
            type=PduType.GNB,
            instance_type="PACKETRUSHER",
            config={"blue_id": self.id}
        ))

    def del_gnb_from_topology(self, area_id: int):
        try:
            self.provider.delete_pdu(f"PACKETRUSHER_GNB_{self.id}_{area_id}")
        except Exception as e:
            self.logger.warning(f"Error deleting PDU: {str(e)}")

    def _create_area(self, area_id: str, sims: List[UESim]):
        if area_id in self.state.areas:
            raise BlueprintNGException(f"Area {area_id} already exists")

        vm = VmResource(
            area=int(area_id),
            name=f"{self.id}_{area_id}_PR",
            image=self.packetrusher_image,
            flavor=self.packetrusher_flavor,
            username="ubuntu",
            password="ubuntu",
            management_network=self.create_config.config.network_endpoints.mgt.net_name,
            additional_networks=[
                self.create_config.config.network_endpoints.n2.net_name,
                self.create_config.config.network_endpoints.n3.net_name,
            ],
            require_port_security_disabled=True
        )
        self.register_resource(vm)
        self.provider.create_vm(vm)
        self.state.areas[area_id] = BluePacketRusherArea(vm=vm, pending_sims=list(sims))
        self.add_gnb_to_topology(int(area_id))

    def _delete_area(self, area_id: str):
        if area_id not in self.state.areas:
            raise BlueprintNGException(f"Area {area_id} not found")
        area = self.state.areas[area_id]
        self.provider.destroy_vm(area.vm)
        self.deregister_resource(area.vm)
        if area.vm_configurator:
            self.deregister_resource(area.vm_configurator)
        del self.state.areas[area_id]
        self.del_gnb_from_topology(int(area_id))

    def _add_sim(self, area_id: str, new_sim: UESim):
        if area_id not in self.state.areas:
            raise BlueprintNGException(f"Area {area_id} not found")
        area = self.state.areas[area_id]

        if area.vm_configurator:
            for sim in area.vm_configurator.sims:
                if sim.imsi == new_sim.imsi:
                    raise BlueprintNGException(f"SIM {new_sim.imsi} already exists in area {area_id}")
            area.vm_configurator.sims.append(new_sim)
            self.provider.configure_vm(area.vm_configurator)
        else:
            for sim in area.pending_sims:
                if sim.imsi == new_sim.imsi:
                    raise BlueprintNGException(f"SIM {new_sim.imsi} already exists in area {area_id}")
            area.pending_sims.append(new_sim)

    def _del_sim(self, area_id: str, imsi: str):
        if area_id not in self.state.areas:
            raise BlueprintNGException(f"Area {area_id} not found")
        area = self.state.areas[area_id]

        if area.vm_configurator:
            for sim in area.vm_configurator.sims:
                if sim.imsi == imsi:
                    area.vm_configurator.sims_to_delete.append(sim)
                    area.vm_configurator.sims.remove(sim)
                    self.provider.configure_vm(area.vm_configurator)
                    return
            raise BlueprintNGException(f"SIM {imsi} not found in area {area_id}")
        else:
            for sim in area.pending_sims:
                if sim.imsi == imsi:
                    area.pending_sims.remove(sim)
                    return
            raise BlueprintNGException(f"SIM {imsi} not found in area {area_id}")

    @day2_function("/add_area", [HttpRequestType.POST])
    def add_area(self, model: PacketRusherBlueprintRequestAddDelArea):
        self._create_area(model.area_id, [])

    @day2_function("/del_area", [HttpRequestType.DELETE])
    def del_area(self, model: PacketRusherBlueprintRequestAddDelArea):
        self._delete_area(model.area_id)

    @day2_function("/configure_gnb", [HttpRequestType.POST])
    def configure_gnb(self, model: GNBPDUConfigure):
        area = self.state.areas[str(model.area)]
        n2_net = self.create_config.config.network_endpoints.n2.net_name
        n3_net = self.create_config.config.network_endpoints.n3.net_name

        n2_addr = area.vm.network_interfaces[n2_net][0].fixed.ip
        n3_addr = area.vm.network_interfaces[n3_net][0].fixed.ip
        n3_nic = area.vm.network_interfaces[n3_net][0].fixed.interface_name

        # Merge pending SIMs with any already configured SIMs
        existing_sims = area.vm_configurator.sims if area.vm_configurator else []
        pending_imsies = {s.imsi for s in existing_sims}
        all_sims = list(existing_sims) + [s for s in area.pending_sims if s.imsi not in pending_imsies]

        if area.vm_configurator:
            self.deregister_resource(area.vm_configurator)

        area.vm_configurator = PacketRusherConfigurator(
            vm_resource=area.vm,
            configuration=model,
            n2_addr=n2_addr,
            n3_addr=n3_addr,
            n3_nic_name=n3_nic,
            sims=all_sims,
            additional_routes=model.additional_routes,
        )
        area.pending_sims.clear()

        self.register_resource(area.vm_configurator)
        self.provider.configure_vm(area.vm_configurator)

    @day2_function("/detach_gnb", [HttpRequestType.POST])
    def detach_gnb(self, model: GNBPDUDetach):
        area = self.state.areas[str(model.area)]
        if area.vm_configurator:
            configurator = PacketRusherConfiguratorDetach(
                vm_resource=area.vm,
                sims=area.vm_configurator.sims,
            )
            self.provider.configure_vm(configurator)

    @day2_function("/add_sim", [HttpRequestType.POST])
    def add_sim(self, model: PacketRusherBlueprintRequestAddSim):
        self._add_sim(model.area_id, model.sim)

    @day2_function("/del_sim", [HttpRequestType.DELETE])
    def del_sim(self, model: PacketRusherBlueprintRequestDelSim):
        self._del_sim(model.area_id, model.imsi)

    def to_dict(self, detailed: bool, include_childrens: bool = False) -> dict:
        if detailed:
            return super().to_dict(detailed, include_childrens)
        else:
            base_dict = super().to_dict(detailed, include_childrens)
            base_dict['areas'] = {}
            for area_id, area in self.state.areas.items():
                sims = area.vm_configurator.sims if area.vm_configurator else area.pending_sims
                base_dict['areas'][area_id] = {
                    "vm": area.vm.access_ip if area.vm else None,
                    "sims": [s.imsi for s in sims],
                }
            return base_dict
