from time import sleep
from typing import Optional

import requests
from pydantic import Field

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_core.blueprints.blueprint_ng import BlueprintNGState, BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core.managers.getters import get_monitoring_manager
from nfvcl_core_models.monitoring.grafana_model import GrafanaServerModel
from nfvcl_core_models.monitoring.loki_model import LokiServerModel
from nfvcl_core_models.monitoring.prometheus_model import PrometheusServerModel
from nfvcl_core_models.resources import VmResource, VmResourceImage, VmResourceAnsibleConfiguration
from nfvcl_models.blueprint_ng.monitoring.monitoring_rest_models import MonitoringCreateModel

MONITORING_BLUE_TYPE = "monitoring"
UBU24_IMAGE_NAME = "monitoring-v0.0.3-ubuntu2404"
UBU24_BASE_IMAGE_URL = "https://images.tnt-lab.unige.it/monitoring/monitoring-v0.0.3-ubuntu2404.qcow2"
UBUNTU_DEFAULT_PASSWORD = "ubuntu"


class VmMonitoringConfigurator(VmResourceAnsibleConfiguration):
    _ansible_builder: AnsiblePlaybookBuilder = AnsiblePlaybookBuilder("Monitoring Day0 Configurator")  # _ in front of the name, so it is not serialized !!!
    grafana_admin_password: str = Field(default="nfvcl")

    def dump_playbook(self) -> str:
        # Grafana configuration block
        self._ansible_builder.add_shell_task(f'grafana-cli --homepath "/usr/share/grafana" admin reset-admin-password {self.grafana_admin_password}')

        return self._ansible_builder.build()


class MonitoringBlueprintNGState(BlueprintNGState):
    """

    """
    password: str = Field(default=UBUNTU_DEFAULT_PASSWORD)
    vm: Optional[VmResource] = Field(default=None)
    configurator: Optional[VmMonitoringConfigurator] = Field(default=None)


@blueprint_type(MONITORING_BLUE_TYPE)
class MonitoringBlueprint(BlueprintNG[MonitoringBlueprintNGState, MonitoringCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = MonitoringBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: MonitoringCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of monitoring blueprint")
        self.state.password = create_model.password

        self.state.vm = VmResource(
            area=create_model.area,
            name=f"{self.id}_{create_model.area}_VM_MONITORING",
            image=VmResourceImage(name=UBU24_IMAGE_NAME, url=UBU24_BASE_IMAGE_URL),
            flavor=create_model.flavor,
            username="ubuntu",
            password=create_model.password,
            management_network=create_model.mgmt_net,
            additional_networks=create_model.data_nets
        )

        # Registering VM for Ubuntu
        self.register_resource(self.state.vm)
        # Creating VM
        self.provider.create_vm(self.state.vm)

        self.state.configurator = VmMonitoringConfigurator(vm_resource=self.state.vm)
        self.register_resource(self.state.configurator)

        self.provider.configure_vm(self.state.configurator)

        if create_model.onboard_on_topology:
            self.provider.topology_manager.add_prometheus(
                PrometheusServerModel(
                    id=self.id,
                    ip=self.state.vm.access_ip,
                    user=self.state.vm.username,
                    password=self.state.vm.password,
                    sd_file_location="/etc/prometheus/sd_targets.yml",
                )
            )
            self.provider.topology_manager.add_grafana(GrafanaServerModel(id=self.id, ip=self.state.vm.access_ip, user="admin", password="nfvcl"))
            self.provider.topology_manager.add_loki(
                LokiServerModel(
                    id=self.id,
                    ip=self.state.vm.access_ip
                )
            )
            not_ready = True
            while not_ready:
                try:
                    response = requests.request(method="GET", url=f"http://{self.state.vm.access_ip}:3000/api/health")
                    if response.status_code == 200:
                        not_ready = False
                except requests.exceptions.ConnectionError:
                    self.logger.info("Waiting for grafana server to be ready...")
                    sleep(3)
            get_monitoring_manager().add_grafana_prometheus(self.id, self.id)
            get_monitoring_manager().add_grafana_loki(self.id)

    def destroy(self):
        super().destroy()
        try:
            if self.create_config.onboard_on_topology:
                self.provider.topology_manager.delete_prometheus(self.id, force=True)
                self.provider.topology_manager.delete_grafana(self.id)
                self.provider.topology_manager.delete_loki(self.id)
        except Exception as e:
            self.logger.warning(f"Error cleaning topology for monitoring blueprint: {e}")
