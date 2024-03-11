from __future__ import annotations
from typing import Optional, List

from topology.topology import build_topology
from blueprints_ng.ansible_builder import AnsibleTask
from blueprints_ng.modules.vyos.config.vyos_nat_conf import VmVyOSNatConfigurator
from models.http_models import HttpRequestType
from blueprints_ng.lcm.blueprint_route_manager import add_route
from starlette.requests import Request
from blueprints.blue_vyos import VyOSDestNATRule, VyOS1to1NATRule, VyOSSourceNATRule
from blueprints_ng.modules.vyos.config.vyos_day0_conf import VmVyOSDay0Configurator
from models.blueprint_ng.vyos.vyos_rest_models import VyOSCreateModel, VyOSBlueprintSNATCreate
from pydantic import Field
from blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface
from blueprints_ng.resources import VmResource, VmResourceImage, VmResourceFlavor

# Use a global variable to define the blueprint type, this will be used in the decorator for the requests supported
# by this blueprint
VYOS_BLUE_TYPE = "vyos"


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
    nat_rules: List[int] = []
    applied_snat_rules: List[VyOSSourceNATRule] = []
    applied_dnat_rules: List[VyOSDestNATRule] = []
    task_list: dict[str, AnsibleTask] = {}


# This decorator is needed to declare a new blueprint type
# The blueprint class need to extend BlueprintNG, the type of the state and create model need to be explicitly passed
# for type hinting to work
@declare_blue_type(VYOS_BLUE_TYPE)
class VyOSBlueprint(BlueprintNG[VyOSBlueprintNGState, VyOSCreateModel]):
    def __init__(self, blueprint_id: str, provider_type: type[BlueprintNGProviderInterface], state_type: type[BlueprintNGState] = VyOSBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, provider_type, state_type)

    def create(self, create_model: VyOSCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of example blueprint")

        # ################################# VMs Example #####################################

        # To describe a new VM create a VmResource object and save it in the state
        self.state.vm_vyos = VmResource(
            area=create_model.area,
            name=f"{self.id}_VM_VyOS",
            image=VmResourceImage(name="VyOS"),
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

        # The same need to be done to apply the configuration to the VMs
        self.provider.configure_vm(self.state.vm_vyos_configurator)

    @classmethod
    def rest_create(cls, msg: VyOSCreateModel, request: Request):
        """
        This is needed for FastAPI to work, don't write code here, just changed the msg type to the correct one
        """
        return cls.api_day0_function(msg, request)


    @classmethod
    def add_snat_rule_rest(cls, msg: VyOSBlueprintSNATCreate, blue_id: str, request: Request):
        """
        This is needed for FastAPI to work, don't write code here, just changed the msg type to the correct one
        """
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(VYOS_BLUE_TYPE, "/snat", [HttpRequestType.POST], add_snat_rule_rest)
    def add_snat_rule(self, model: VyOSBlueprintSNATCreate):
        _topology = build_topology()
        network = _topology.get_network(model.rule.outbound_network)

        # TODO need to obtain data from ansible before this function can work

        self.state.vm_vyos_nat_configurator.add_snat_rule(model.rule)
        self.provider.configure_vm(self.state.vm_vyos_configurator)
