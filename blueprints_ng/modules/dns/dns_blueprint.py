from typing import Optional
from models.blueprint_ng.dns.dns_rest_models import DNSCreateModel
from starlette.requests import Request
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.resources import VmResource, VmResourceImage, VmResourceFlavor
from pydantic import Field
from blueprints_ng.blueprint_ng import BlueprintNGState, BlueprintNG

DNS_BLUE_TYPE = "dns"
BASE_IMAGE = "dns-server"
BASE_IMAGE_URL = "http://images.tnt-lab.unige.it/dns-server/dns-server-v0.0.1.qcow2"
DNS_DEFAULT_PASSWORD = "dns-server-pwd"

class DNSBlueprintNGState(BlueprintNGState):
    """

    """
    password: str = Field(default=DNS_DEFAULT_PASSWORD)
    vm: Optional[VmResource] = Field(default=None)


@declare_blue_type(DNS_BLUE_TYPE)
class DNSBlueprint(BlueprintNG[DNSBlueprintNGState, DNSCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = DNSBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: DNSCreateModel):
        """
        """
        super().create(create_model)
        self.logger.info("Starting creation of example blueprint")

        # ################################# VMs Example #####################################

        # To describe a new VM create a VmResource object and save it in the state
        self.state.vm = VmResource(
            area=create_model.area,
            name=f"{self.id}_VM_DNS_SERVER",
            image=VmResourceImage(name=BASE_IMAGE, url=BASE_IMAGE_URL),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password=create_model.password,
            management_network=create_model.mgmt_net,
            additional_networks=create_model.data_nets
        )
        # When a Resource is added it also need to be registered
        # This is MANDATORY
        self.register_resource(self.state.vm)

        self.provider.create_vm(self.state.vm)


    @classmethod
    def rest_create(cls, msg: DNSCreateModel, request: Request):
        """
        Creates a K8S cluster using the NFVCL blueprint
        """
        return cls.api_day0_function(msg, request)
