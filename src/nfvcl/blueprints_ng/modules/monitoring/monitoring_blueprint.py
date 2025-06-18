from typing import Optional

from pydantic import Field

from nfvcl_core.blueprints.blueprint_ng import BlueprintNGState, BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.resources import VmResource, VmResourceImage
from nfvcl_models.blueprint_ng.monitoring.monitoring_rest_models import MonitoringCreateModel

MONITORING_BLUE_TYPE = "monitoring"
UBU24_IMAGE_NAME = "monitoring-v0.0.1-ubuntu2404"
UBU24_BASE_IMAGE_URL = "https://images.tnt-lab.unige.it/monitoring/monitoring-v0.0.1-ubuntu2404.qcow2"
UBUNTU_DEFAULT_PASSWORD = "ubuntu"

class MonitoringBlueprintNGState(BlueprintNGState):
    """

    """
    password: str = Field(default=UBUNTU_DEFAULT_PASSWORD)
    vm: Optional[VmResource] = Field(default=None)
    # configurator: Optional[VmUbuntuConfigurator] = Field(default=None)


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
            image=VmResourceImage(name=UBU24_IMAGE_NAME, url=UBU24_BASE_IMAGE_URL, check_sha512sum=True),
            flavor=create_model.flavor,
            username="ubuntu",
            password=create_model.password,
            management_network=create_model.mgmt_net,
            additional_networks=create_model.data_nets
        )

        #Registering VM for Ubuntu
        self.register_resource(self.state.vm)
        #Creating VM
        self.provider.create_vm(self.state.vm)
        # No need for configuration, at least for now.
