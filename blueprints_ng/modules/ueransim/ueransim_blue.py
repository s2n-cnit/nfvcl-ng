from __future__ import annotations

from typing import List, Optional, Dict

from models.http_models import HttpRequestType

from blueprints_ng.lcm.blueprint_route_manager import add_route
from pydantic import Field
from starlette.requests import Request

from blueprints_ng.ansible_builder import AnsiblePlaybookBuilder
from blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.modules.ueransim.ueransim_models import UeransimBlueprintRequestInstance, UeransimBlueprintRequestConfigureGNB
from blueprints_ng.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration, \
    NetResource
from blueprints_ng.utils import rel_path
from models.base_model import NFVCLBaseModel
from models.ueransim.blueprint_ueransim_model import UeransimSim

UERANSIM_BLUE_TYPE = "ueransim"


class UeransimUe(NFVCLBaseModel):
    vm_ue: Optional[VmResource] = Field(default=None)
    vm_ue_configurators: List[UeransimUEConfigurator] = Field(default_factory=list)


class UeransimArea(NFVCLBaseModel):
    vm_gnb: Optional[VmResource] = Field(default=None)
    vm_gnb_configurator: Optional[UeransimGNBConfigurator] = Field(default=None)
    ues: List[UeransimUe] = Field(default_factory=list)
    radio_net: Optional[NetResource] = Field(default=None)


class UeransimBlueprintNGState(BlueprintNGState):
    areas: Dict[str, UeransimArea] = Field(default_factory=dict)


class UeransimGNBConfigurator(VmResourceAnsibleConfiguration):
    configuration: UeransimBlueprintRequestConfigureGNB = Field()

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook UeransimGNBConfigurator")

        ansible_builder.add_template_task(rel_path("config/gnb_conf_file.jinja2"), "/opt/UERANSIM/gnb.conf")
        ansible_builder.set_vars_from_fields(self.configuration)

        return ansible_builder.build()


class UeransimUEConfigurator(VmResourceAnsibleConfiguration):
    sim_num: int = Field()
    sim: UeransimSim = Field()
    gnbSearchList: List[str] = Field()

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder(f"Playbook UeransimUEConfigurator for sim {self.sim_num}")

        ue_sim_config_path = f"/opt/UERANSIM/ue-sim-{self.sim_num}.conf"

        ansible_builder.add_template_task(rel_path("config/ue_conf_file.jinja2"), ue_sim_config_path)

        ansible_builder.set_var("sim", self.sim)
        ansible_builder.set_var("gnbSearchList", self.gnbSearchList)

        # Create a new service to start the UE with this SIM

        ue_sim_service_path = f"/etc/systemd/system/ueransim-ue-sim-{self.sim_num}.service"

        ansible_builder.add_copy_task(
            "/etc/systemd/system/ueransim-ue.service",
            ue_sim_service_path,
            remote_src=True
        )

        ansible_builder.add_replace_task(ue_sim_service_path, "/opt/UERANSIM/ue.conf", ue_sim_config_path)
        ansible_builder.add_replace_task(ue_sim_service_path, "UERANSIM UE", f"UERANSIM UE SIM {self.sim_num}")

        # Reload services

        ansible_builder.add_shell_task("systemctl daemon-reload")

        return ansible_builder.build()


@declare_blue_type(UERANSIM_BLUE_TYPE)
class UeransimBlueprintNG(BlueprintNG[UeransimBlueprintNGState, UeransimBlueprintRequestInstance]):
    # RADIO_NET_CIDR = '10.168.0.0/16'
    # RADIO_NET_CIDR_START = '10.168.0.2'
    # RADIO_NET_CIDR_END = '10.168.255.253'

    ueransim_image = VmResourceImage(name="ueransim-v3.2.6-dev", url="http://images.tnt-lab.unige.it/ueransim/ueransim-v3.2.6-dev.qcow2")
    ueransim_flavor = VmResourceFlavor(vcpu_count='2', memory_mb='4096', storage_gb='10')

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = UeransimBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: UeransimBlueprintRequestInstance):
        super().create(create_model)

        self.logger.info("Starting creation of UERANSIM blueprint")

        for area in create_model.areas:
            # Using area id to build a unique CIDR
            # TODO find a better way, what about areas with id > 255 ?
            radio_network_name = f"radio_{self.id}_{area.id}"
            network = NetResource(area=area.id, name=radio_network_name, cidr=f"10.168.{area.id}.0/24")
            self.register_resource(network)
            self.provider.create_net(network)

            vm_gnb = VmResource(
                area=area.id,
                name=f"{self.id}_{area.id}_GNB",
                image=self.ueransim_image,
                flavor=self.ueransim_flavor,
                username="ubuntu",
                password="ubuntu",
                management_network=create_model.config.network_endpoints.mgt,
                additional_networks=[create_model.config.network_endpoints.wan, radio_network_name]
            )
            self.register_resource(vm_gnb)
            self.provider.create_vm(vm_gnb)

            ueransim_ue_list: List[UeransimUe] = []

            for ue in area.ues:
                vm_ue = VmResource(
                    area=area.id,
                    name=f"{self.id}_{area.id}_UE_{ue.id}",
                    image=self.ueransim_image,
                    flavor=self.ueransim_flavor,
                    username="ubuntu",
                    password="ubuntu",
                    management_network=create_model.config.network_endpoints.mgt,
                    additional_networks=[create_model.config.network_endpoints.wan, radio_network_name]
                )
                self.register_resource(vm_ue)

                self.provider.create_vm(vm_ue)

                vm_ue_configurators: List[UeransimUEConfigurator] = []

                for sim_num, sim in enumerate(ue.sims):
                    vm_ue_configurator = UeransimUEConfigurator(
                        vm_resource=vm_ue,
                        sim_num=sim_num,
                        sim=sim,
                        gnbSearchList=[vm_gnb.network_interfaces[radio_network_name].fixed.ip]
                    )
                    self.register_resource(vm_ue_configurator)
                    self.provider.configure_vm(vm_ue_configurator)
                    vm_ue_configurators.append(vm_ue_configurator)

                ueransim_ue = UeransimUe(vm_ue=vm_ue, vm_ue_configurators=vm_ue_configurators)
                ueransim_ue_list.append(ueransim_ue)

            self.state.areas[str(area.id)] = UeransimArea(vm_gnb=vm_gnb, ues=ueransim_ue_list, radio_net=network)

    @classmethod
    def rest_create(cls, msg: UeransimBlueprintRequestInstance, request: Request):
        return cls.api_day0_function(msg, request)

    @classmethod
    def configure_gnb_endpoint(cls, msg: UeransimBlueprintRequestConfigureGNB, blue_id: str, request: Request):
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(UERANSIM_BLUE_TYPE, "/configure_gnb", [HttpRequestType.POST], configure_gnb_endpoint)
    def configure_gnb(self, model: UeransimBlueprintRequestConfigureGNB):
        area = self.state.areas[str(model.area)]

        area.vm_gnb_configurator = UeransimGNBConfigurator(vm_resource=area.vm_gnb, configuration=model)
        self.register_resource(area.vm_gnb_configurator)

        self.provider.configure_vm(area.vm_gnb_configurator)
