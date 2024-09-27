from __future__ import annotations

from pydantic import Field

from nfvcl.blueprints_ng.ansible_builder import AnsiblePlaybookBuilder
from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGCreateModel, BlueprintNGState
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.pdu_configurators.implementations.generic_linux_pdu_configurator import GenericLinuxPDUConfigurator
from nfvcl.blueprints_ng.resources import PDUResourceAnsibleConfiguration


#
class ExamplePDUCreateModel(BlueprintNGCreateModel):
    """
    This class represent the model for the create request
    """
    pdu_name: str = Field()


class ExamplePDUBlueprintNGState(BlueprintNGState):
    pass


class ExamplePDUConfigurator(PDUResourceAnsibleConfiguration):
    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook ExamplePDUConfigurator")

        ansible_builder.add_shell_task("echo '123' > /tmp/file1")

        # Build the playbook and return it
        return ansible_builder.build()


# This decorator is needed to declare a new blueprint type
# The blueprint class need to extend BlueprintNG, the type of the state and create model need to be explicitly passed
# for type hinting to work
@blueprint_type("example_pdu")
class ExamplePDUBlueprintNG(BlueprintNG[ExamplePDUBlueprintNGState, ExamplePDUCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = ExamplePDUBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: ExamplePDUCreateModel):
        """
        This docstring for the create function will be shown on Swagger
        """
        super().create(create_model)
        self.logger.info("Starting creation of example_pdu blueprint")

        # Find the PDU
        pdu = self.provider.find_by_name(create_model.pdu_name)
        # Lock the PDU to this blueprint
        self.provider.lock_pdu(pdu)
        # Get the configurator
        configurator: GenericLinuxPDUConfigurator = self.provider.get_pdu_configurator(pdu)
        # Run a configurator function
        configurator.run_ansible(ExamplePDUConfigurator().dump_playbook())

