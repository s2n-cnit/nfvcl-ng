from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.ubuntu.config.ubuntu_configurator import VmUbuntuConfigurator
from nfvcl_core.blueprints.blueprint_ng import BlueprintNGState, BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl_core_models.http_models import HttpRequestType
from nfvcl_core_models.resources import VmResource, VmResourceImage
from nfvcl_models.blueprint_ng.ubuntu.ubuntu_rest_models import UbuntuCreateModel, UbuntuInstallAptModel
from nfvcl_models.blueprint_ng.ubuntu.ubuntu_rest_models import UbuntuVersion

UBUNTU_BLUE_TYPE = "ubuntu"
UBU22_IMAGE_NAME = "ubuntu-lab-22-v0.1.4"
UBU24_IMAGE_NAME = "ubuntu-lab-24-v0.1.4"
UBU22_BASE_IMAGE_URL = "https://images.tnt-lab.unige.it/ubuntu-lab/ubuntu-lab-v0.1.4-ubuntu2204.qcow2"
UBU24_BASE_IMAGE_URL = "https://images.tnt-lab.unige.it/ubuntu-lab/ubuntu-lab-v0.1.4-ubuntu2404.qcow2"
UBUNTU_DEFAULT_PASSWORD = "ubuntu"

class UbuntuBlueprintNGState(BlueprintNGState):
    """

    """
    password: str = Field(default=UBUNTU_DEFAULT_PASSWORD)
    vm: Optional[VmResource] = Field(default=None)
    configurator: Optional[VmUbuntuConfigurator] = Field(default=None)


@blueprint_type(UBUNTU_BLUE_TYPE)
class UbuntuBlueprint(BlueprintNG[UbuntuBlueprintNGState, UbuntuCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = UbuntuBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: UbuntuCreateModel):
        """
        Creates a K8S cluster using the NFVCL blueprint
        """
        super().create(create_model)
        self.logger.info("Starting creation of example blueprint")
        self.state.password = create_model.password

        # Ubuntu 22 or 24?
        match create_model.version:
            case UbuntuVersion.UBU24.value:
                image_name = UBU24_IMAGE_NAME
                image_url = UBU24_BASE_IMAGE_URL
            case UbuntuVersion.UBU22.value:
                image_name = UBU22_IMAGE_NAME
                image_url = UBU22_BASE_IMAGE_URL
            case _:
                image_name = UBU24_IMAGE_NAME
                image_url = UBU24_BASE_IMAGE_URL


        self.state.vm = VmResource(
            area=create_model.area,
            name=f"{self.id}_VM_UBUNTU",
            image=VmResourceImage(name=image_name, url=image_url, check_sha512sum=True),
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

        self.state.configurator = VmUbuntuConfigurator(vm_resource=self.state.vm)
        self.register_resource(self.state.configurator)

    @day2_function("/apt_install", [HttpRequestType.PUT])
    def apt_install(self, model: UbuntuInstallAptModel):
        self.state.configurator.install_apt_packages(model.packages)
        self.provider.configure_vm(self.state.configurator)


