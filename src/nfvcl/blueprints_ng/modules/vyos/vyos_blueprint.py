from __future__ import annotations

from typing import Optional

from pydantic import Field

from nfvcl.models.blueprint_ng.vyos.vyos_models import VyOSSourceNATRule
from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type, day2_function
from nfvcl.blueprints_ng.modules.vyos.config.vyos_day0_conf import VmVyOSDay0Configurator
from nfvcl.blueprints_ng.modules.vyos.config.vyos_nat_conf import VmVyOSNatConfigurator
from nfvcl.blueprints_ng.resources import VmResource, VmResourceImage, VmResourceFlavor
from nfvcl.models.blueprint_ng.vyos.vyos_models import VyOSNetworkNotConnectedToVM, VyOSInterfaceNotExisting
from nfvcl.models.blueprint_ng.vyos.vyos_rest_models import VyOSCreateModel
from nfvcl.models.http_models import HttpRequestType

# Use a global variable to define the blueprint type, this will be used in the decorator for the requests supported
# by this blueprint
VYOS_BLUE_TYPE = "vyos"
VYOS_BASE_NAME = "VyOS"
VYOS_BASE_IMAGE_URL = "https://images.tnt-lab.unige.it/k8s/k8s-v0.0.1.qcow2"


class VyOSBlueprintNGState(BlueprintNGState):
    """
    This class represent the current state of the blueprint, the data contained in this class will be saved to the DB

    Every Resource should be stored in a variable in this class to be able to access it after the initial creation

    Everything in this class should be serializable by Pydantic

    Every field need to be Optional because the state is created empty
    """
    vm_vyos: Optional[VmResource] = Field(default=None)
    vm_vyos_configurator: Optional[VmVyOSDay0Configurator] = Field(default=None)

    vm_vyos_nat_configurator: Optional[VmVyOSNatConfigurator] = Field(default=None)


# This decorator is needed to declare a new blueprint type
# The blueprint class need to extend BlueprintNG, the type of the state and create model need to be explicitly passed
# for type hinting to work
@blueprint_type(VYOS_BLUE_TYPE)
class VyOSBlueprint(BlueprintNG[VyOSBlueprintNGState, VyOSCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = VyOSBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: VyOSCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of example blueprint")

        # ################################# VMs Example #####################################

        # To describe a new VM create a VmResource object and save it in the state
        self.state.vm_vyos = VmResource(
            area=create_model.area,
            name=f"{self.id}_VM_VyOS",
            image=VmResourceImage(name=VYOS_BASE_NAME, url=VYOS_BASE_IMAGE_URL),
            flavor=VmResourceFlavor(memory_mb="4096", storage_gb='16', vcpu_count='2'),
            username="vyos",
            password="vyos",
            management_network=create_model.mgmt_net,
            additional_networks=create_model.data_nets
        )
        # When a Resource is added it also need to be registered
        # This is MANDATORY
        self.register_resource(self.state.vm_vyos)

        # Until this point nothing is really being done on the VIM, the resource and their configuration is defined, registered and saved in the state
        # but is not applied yet

        # To create VMs use the create_vm method of the provider
        # Every provider method is synchronous: the method will return only when the operation is finished
        self.provider.create_vm(self.state.vm_vyos) # TODO should retrieve ansible info from

        # To configure a VM create a new configurator object and pass the VmResource as the 'vm_resource' arg
        self.state.vm_vyos_configurator = VmVyOSDay0Configurator(vm_resource=self.state.vm_vyos)
        self.register_resource(self.state.vm_vyos_configurator)

        # To configure a VM create a new configurator object and pass the VmResource as the 'vm_resource' arg
        self.state.vm_vyos_nat_configurator = VmVyOSNatConfigurator(vm_resource=self.state.vm_vyos)
        self.register_resource(self.state.vm_vyos_nat_configurator)

        self.state.vm_vyos_configurator.initial_setup()
        self.provider.configure_vm(self.state.vm_vyos_configurator)

    @day2_function("/snat", [HttpRequestType.POST])
    def add_snat_rule(self, model: VyOSSourceNATRule):
        # Checks
        if self.state.vm_vyos.get_network_interface_by_name(model.outbound_interface) is None:
            raise VyOSInterfaceNotExisting(model.outbound_interface)
        if not self.state.vm_vyos.check_if_network_connected_by_cidr(model.source_address):
            raise VyOSNetworkNotConnectedToVM(model.source_address)

        self.state.vm_vyos_nat_configurator.add_snat_rule(model)
        self.provider.configure_vm(self.state.vm_vyos_nat_configurator)
