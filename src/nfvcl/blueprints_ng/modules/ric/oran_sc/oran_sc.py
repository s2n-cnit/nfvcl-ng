import time
from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_ric import DeployedRICInfo
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_ric_vm import Generic5GRICVMBlueprintNGState, Generic5GRICVMBlueprintNG
from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_common.utils.blue_utils import rel_path
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address
from nfvcl_core_models.resources import VmResourceImage, VmResourceFlavor, VmResource, VmResourceAnsibleConfiguration
from nfvcl_models.blueprint_ng.g5.ric import RICBlueCreateModel, RICNetworkInfo, RICRunXappModel, RICOnboardXappModel, RicDeleteXappModel

ORAN_SC_RIC_BLUE_TYPE = "oran_sc"
ORAN_SC_IMAGE_NAME = "OranScRic"
ORAN_SC_IMAGE_URL = "https://images.tnt-lab.unige.it/oran-sc-ric/oran-sc-ric-1.0.0-ubuntu2204.qcow2"


class OranScRicConfigurator(VmResourceAnsibleConfiguration):
    compose_name: Optional[str] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook OranRunRicConfigurator")

        ansible_builder.set_var("compose_name", self.compose_name)

        ansible_builder.add_template_task(rel_path("start_sh.jinja2"), "/root/oran/ric-base/start.sh")
        ansible_builder.add_template_task(rel_path("stop_sh.jinja2"), "/root/oran/ric-base/stop.sh")
        ansible_builder.add_template_task(rel_path("ric_service.jinja2"), "/etc/systemd/system/ric.service")

        ansible_builder.add_service_task("ric", ServiceState.RESTARTED, True)

        return ansible_builder.build()


class OranXappConfigurator(VmResourceAnsibleConfiguration):
    xapp_name: Optional[str] = Field(default=None)
    xapp_url: Optional[str] = Field(default=None)
    compose_name: Optional[str] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook OranRunXappConfigurator")

        ansible_builder.set_var("compose_name", self.compose_name)
        ansible_builder.set_var("xapp_name", self.xapp_name)
        ansible_builder.set_var("xapp_url", self.xapp_url)

        ansible_builder.add_shell_task(f"wget {self.xapp_url} -O /root/oran/xapp-runner/xApps/python/{self.xapp_name}")

        ansible_builder.add_template_task(rel_path("start_sh.jinja2"), f"/root/oran/xapp-runner/start_{self.xapp_name}.sh")
        ansible_builder.add_template_task(rel_path("stop_sh.jinja2"), f"/root/oran/xapp-runner/stop_{self.xapp_name}.sh")
        ansible_builder.add_template_task(rel_path("xapp_service.jinja2"), f"/etc/systemd/system/xapp_{self.xapp_name}.service")
        ansible_builder.add_shell_task("systemctl daemon-reload")

        return ansible_builder.build()


class OranRunXappConfigurator(VmResourceAnsibleConfiguration):
    xapp_name: Optional[str] = Field(default=None)
    compose_name: Optional[str] = Field(default=None)
    command: Optional[str] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook OranRunXappRunConfigurator")

        ansible_builder.set_var("xapp_name", self.xapp_name)
        ansible_builder.set_var("compose_name", self.compose_name)
        ansible_builder.set_var("command", self.command)

        ansible_builder.add_template_task(rel_path("xapp_compose.jinja2"), f"/root/oran/xapp-runner/{self.compose_name}")
        ansible_builder.add_service_task(f"xapp_{self.xapp_name}", ServiceState.RESTARTED, True)

        return ansible_builder.build()


class OranDeleteXappConfigurator(VmResourceAnsibleConfiguration):
    xapp_name: Optional[str] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook OranDeleteXappConfigurator")

        ansible_builder.set_var("xapp_name", self.xapp_name)
        ansible_builder.add_service_task(f"xapp_{self.xapp_name}", ServiceState.STOPPED, True)
        ansible_builder.add_shell_task(f"rm /root/oran/xapp-runner/xApps/python/{self.xapp_name}")

        return ansible_builder.build()


class OranLogsReaderConfigurator(VmResourceAnsibleConfiguration):
    container_name: Optional[str] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook OranLogsReaderConfigurator")
        ansible_builder.add_run_command_and_gather_output_tasks(command=f"docker logs {self.container_name} 2>&1", output_var_name=f"{self.container_name}_logs")
        return ansible_builder.build()


class OranScBlueprintNGState(Generic5GRICVMBlueprintNGState):
    ric_vm_configurators: Optional[OranScRicConfigurator] = Field(default=None)
    ric_vm_xapp_configurators: Optional[OranXappConfigurator] = Field(default=None)
    ric_vm_xapp_run_configurators: Optional[OranRunXappConfigurator] = Field(default=None)
    ric_vm_delete_xapp_configurators: Optional[OranDeleteXappConfigurator] = Field(default=None)
    ric_vm_logs_configurators: Optional[OranLogsReaderConfigurator] = Field(default=None)


@blueprint_type(ORAN_SC_RIC_BLUE_TYPE)
class OranScBlueprint(Generic5GRICVMBlueprintNG[OranScBlueprintNGState, RICBlueCreateModel]):

    def __init__(self, blueprint_id: str, state_type: type[Generic5GRICVMBlueprintNGState] = OranScBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_ric(self):
        self.logger.info("Starting creation of Oran-sc-ric blueprint")

        # To describe a new VM create a VmResource object and save it in the state
        ric_vm = VmResource(
            area=self.state.current_config.area_id,
            name=f"{self.id}_ORAN_SC_RIC_{self.state.current_config.area_id}",
            image=VmResourceImage(name=ORAN_SC_IMAGE_NAME, url=ORAN_SC_IMAGE_URL),
            flavor=VmResourceFlavor(vcpu_count='4', memory_mb='8192', storage_gb='10'),
            username="ubuntu",
            password="ubuntu",
            management_network=self.state.current_config.mgt.net_name,
            additional_networks=[self.state.current_config.e2.net_name]
        )
        self.register_resource(ric_vm)
        self.provider.create_vm(ric_vm)
        self.state.vm_resources[ric_vm.id] = ric_vm

        self.state.ric_vm_configurators = OranScRicConfigurator(vm_resource=ric_vm)
        self.register_resource(self.state.ric_vm_configurators)

        self.state.ric_vm_xapp_configurators = OranXappConfigurator(vm_resource=ric_vm)
        self.register_resource(self.state.ric_vm_xapp_configurators)

        self.state.ric_vm_xapp_run_configurators = OranRunXappConfigurator(vm_resource=ric_vm)
        self.register_resource(self.state.ric_vm_xapp_run_configurators)

        self.state.ric_vm_delete_xapp_configurators = OranDeleteXappConfigurator(vm_resource=ric_vm)
        self.register_resource(self.state.ric_vm_delete_xapp_configurators)

        self.state.ric_vm_logs_configurators = OranLogsReaderConfigurator(vm_resource=ric_vm)
        self.register_resource(self.state.ric_vm_logs_configurators)

        self.update_ric()

    def update_ric(self):
        self.state.ric_vm_configurators.compose_name = "docker-compose.yml"
        self.provider.configure_vm(self.state.ric_vm_configurators)
        self.update_ric_info()

    def update_ric_info(self):
        ric_vm = next(iter(self.state.vm_resources.values()))

        deployed_ric_info = DeployedRICInfo(
            area=self.state.current_config.area_id,
            vm_resource_id=ric_vm.id,
            # vm_configurator_id=self.state.ric_vm_configurators.id,
            network_info=RICNetworkInfo(
                e2_ip=SerializableIPv4Address(ric_vm.network_interfaces[self.state.current_config.e2.net_name][0].fixed.ip),
                mgt_ip=SerializableIPv4Address(ric_vm.network_interfaces[self.state.current_config.mgt.net_name][0].fixed.ip))
        )
        self.state.ric = deployed_ric_info

    def onboard_xapp_ric(self, xapp_data: RICOnboardXappModel):
        if xapp_data.xapp_name in self.state.xapps:
            raise ValueError(f"Xapp {xapp_data.xapp_name} already onboarded")
        self.state.ric_vm_xapp_configurators.compose_name = f"docker-{xapp_data.xapp_name}-compose.yml"
        self.state.ric_vm_xapp_configurators.xapp_url = xapp_data.xapp_url
        self.state.ric_vm_xapp_configurators.xapp_name = xapp_data.xapp_name
        self.state.xapps.append(xapp_data.xapp_name)
        self.provider.configure_vm(self.state.ric_vm_xapp_configurators)

    def run_xapp_ric(self, xapp: RICRunXappModel):
        if xapp.xapp_name in self.state.xapps:
            self.state.ric_vm_xapp_run_configurators.xapp_name = xapp.xapp_name
            self.state.ric_vm_xapp_run_configurators.compose_name = f"docker-{xapp.xapp_name}-compose.yml"
            self.state.ric_vm_xapp_run_configurators.command = xapp.command
            self.provider.configure_vm(self.state.ric_vm_xapp_run_configurators)
        else:
            raise ValueError(f"Xapp {xapp.xapp_name} not onboarded")

    def get_xapps_ric(self):
        return self.state.xapps

    def delete_xapp_ric(self, xapp: RicDeleteXappModel):
        if xapp.xapp_name in self.state.xapps:
            self.state.ric_vm_delete_xapp_configurators.xapp_name = xapp.xapp_name
            self.provider.configure_vm(self.state.ric_vm_delete_xapp_configurators)
            self.state.xapps.remove(xapp.xapp_name)
        else:
            raise ValueError(f"Xapp {xapp.xapp_name} not onboarded")

    def wait_gnb_connection_ric(self):
        time.sleep(5)
        # gnb_to_wait = self.state.gnb_ids[self.state.current_config.gnb_pdu_name]
        # self.state.ric_vm_logs_configurators.container_name = "ric_rtmgr_sim"
        #
        # max_retries = 5
        # retry_count = 0
        #
        # while retry_count < max_retries:
        #     fact_cache = self.provider.configure_vm(self.state.ric_vm_logs_configurators)
        #     if fact_cache.get(f"{self.state.ric_vm_logs_configurators.container_name}_logs"):
        #         logs = fact_cache[f"{self.state.ric_vm_logs_configurators.container_name}_logs"]
        #         for line in logs.split("\n"):
        #             if gnb_to_wait in line:
        #                 return
        #     retry_count += 1
        #     if retry_count < max_retries:
        #         time.sleep(3)
        #
        #
        # raise TimeoutError(f"GNB {gnb_to_wait} not found in logs after {max_retries} attempts")
