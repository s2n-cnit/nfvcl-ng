from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.ubuntu.config.ubuntu_configurator import VmUbuntuConfigurator
from nfvcl_core.blueprints.blueprint_ng import BlueprintNGState, BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_core_models.resources import VmResource, VmResourceImage
from nfvcl_models.blueprint_ng.simulaqron.simulaqron_rest_models import SimulaqronCreateModel
from nfvcl_models.blueprint_ng.ubuntu.ubuntu_rest_models import UbuntuInstallAptModel

SIMULAQRON_BLUE_TYPE = "simulaqron"
SIMULAQRON_IMAGE_NAME = "simulaqron-v0.0.1"
SIMULAQRON_BASE_IMAGE_URL = "https://images.tnt-lab.unige.it/simulaqron/simulaqron-v0.0.1-ubuntu2604.qcow2"
SIMULAQRON_DEFAULT_PASSWORD = "ubuntu"

class SimulaqronBlueprintNGState(BlueprintNGState):
    """

    """
    password: str = Field(default=SIMULAQRON_DEFAULT_PASSWORD)
    vm: Optional[VmResource] = Field(default=None)
    configurator: Optional[VmUbuntuConfigurator] = Field(default=None)


@blueprint_type(SIMULAQRON_BLUE_TYPE)
class SimulaqronBlueprint(BlueprintNG[SimulaqronBlueprintNGState, SimulaqronCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = SimulaqronBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: SimulaqronCreateModel):
        """
        Creates a K8S cluster using the NFVCL blueprint
        """
        super().create(create_model)
        self.logger.info("Starting creation of simulaqron blueprint")
        self.state.password = create_model.password

        image_name = SIMULAQRON_IMAGE_NAME
        image_url = SIMULAQRON_BASE_IMAGE_URL

        self.state.vm = VmResource(
            area=create_model.area,
            name=f"{self.id}_VM_SIMULAQRON",
            image=VmResourceImage(name=image_name, url=image_url, check_sha512sum=False),
            flavor=create_model.flavor,
            username="ubuntu",
            password=create_model.password,
            management_network=create_model.mgmt_net,
            additional_networks=create_model.data_nets
        )

        #Registering VM for Simulaqron
        self.register_resource(self.state.vm)
        #Creating VM
        self.provider.create_vm(self.state.vm)
        # No need for configuration, at least for now.

        self.state.configurator = VmUbuntuConfigurator(vm_resource=self.state.vm)
        self.register_resource(self.state.configurator)

    @day2_function("/apt_install", [HttpRequestType.PUT])
    def apt_install(self, model: UbuntuInstallAptModel):
        self.state.configurator.install_apt_packages(model.packages)
        self.provider.configure_vm(self.state.configurator)


