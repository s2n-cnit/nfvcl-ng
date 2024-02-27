from __future__ import annotations
from typing import List, Optional

from blueprints_ng.utils import rel_path

from blueprints_ng.ansible_builder import AnsiblePlaybookBuilder
from pydantic import Field
from starlette.requests import Request

from blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGCreateModel, BlueprintNGState
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface
from blueprints_ng.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration, HelmChartResource

# Use a global variable to define the blueprint type, this will be used in the decorator for the requests supported
# by this blueprint
EXAMPLE_BLUE_TYPE = "example"


class ExampleCreateModel(BlueprintNGCreateModel):
    """
    This class represent the model for the create request
    """
    mgmt_net: str = Field()
    data_net: str = Field()
    chart_value: str = Field()


class ExampleBlueprintNGState(BlueprintNGState):
    """
    This class represent the current state of the blueprint, the data contained in this class will be saved to the DB

    Every Resource should be stored in a variable in this class to be able to access it after the initial creation

    Everything in this class should be serializable by Pydantic

    Every field need to be Optional because the state is created empty
    """
    vm_ubuntu1: Optional[VmResource] = Field(default=None)
    vm_ubuntu2: Optional[VmResource] = Field(default=None)
    vm_ubuntu1_configurator: Optional[ExampleVmUbuntuConfigurator] = Field(default=None)
    vm_ubuntu2_configurator: Optional[ExampleVmUbuntuConfigurator] = Field(default=None)

    mqtt_helm_chart: Optional[HelmChartResource] = Field(default=None)


class ExampleVmUbuntuConfigurator(VmResourceAnsibleConfiguration):
    """
    This class is an example for an Ansible configurator for a VM

    The fields in this class will be saved to the DB and can be used to customize the configuration at runtime
    """
    file_content: str = Field(default="")
    value1: str = Field(default="")
    value_list: List[str] = Field(default=[])

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string
        """

        # While not mandatory it is recommended to use AnsiblePlaybookBuilder to create the playbook
        ansible_builder = AnsiblePlaybookBuilder("Playbook ExampleVmUbuntuConfigurator")

        # With the rel_path function you can use paths relative to this file (example_blue.py) location
        ansible_builder.add_tasks_from_file(rel_path("example_playbook.yaml"))

        # Set the playbook variables (can be done anywhere in this method, but it needs to be before the build)
        ansible_builder.set_var("file_content", self.file_content)
        ansible_builder.set_var("value1", self.value1)
        ansible_builder.set_var("value_list", self.value_list)

        # This will compile the 'example_conf_file.jinja2' file using jinja2 and save the result in the '/example_conf.cfg' file on the server
        ansible_builder.add_template_task(rel_path("example_conf_file.jinja2"), "/example_conf.cfg")

        # Build the playbook and return it
        return ansible_builder.build()


# This decorator is needed to declare a new blueprint type
# The blueprint class need to extend BlueprintNG, the type of the state and create model need to be explicitly passed
# for type hinting to work
@declare_blue_type(EXAMPLE_BLUE_TYPE)
class ExampleBlueprintNG(BlueprintNG[ExampleBlueprintNGState, ExampleCreateModel]):
    def __init__(self, blueprint_id: str, provider_type: type[BlueprintNGProviderInterface], state_type: type[BlueprintNGState] = ExampleBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, provider_type, state_type)

    def create(self, create_model: ExampleCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of example blueprint")

        # ################################# VMs Example #####################################

        # To describe a new VM create a VmResource object and save it in the state
        self.state.vm_ubuntu1 = VmResource(
            area=0,
            name=f"{self.id}_VM_Ubuntu_1",
            image=VmResourceImage(name="ubuntu2204"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="ubuntu",
            management_network=create_model.mgmt_net,
            additional_networks=[create_model.data_net]
        )
        # When a Resource is added it also need to be registered
        # This is MANDATORY
        self.register_resource(self.state.vm_ubuntu1)

        self.state.vm_ubuntu2 = VmResource(
            area=0,
            name=f"{self.id}_VM_Ubuntu_2",
            image=VmResourceImage(name="ubuntu2204"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="ubuntu",
            management_network=create_model.mgmt_net,
            additional_networks=[create_model.data_net]
        )
        self.register_resource(self.state.vm_ubuntu2)

        # Until this point nothing is really being done on the VIM, the resource and their configuration is defined, registered and saved in the state
        # but is not applied yet

        # To create VMs use the create_vm method of the provider
        # Every provider method is synchronous: the method will return only when the operation is finished
        self.provider.create_vm(self.state.vm_ubuntu1)
        self.provider.create_vm(self.state.vm_ubuntu2)

        # To configure a VM create a new configurator object and pass the VmResource as the 'vm_resource' arg
        self.state.vm_ubuntu1_configurator = ExampleVmUbuntuConfigurator(vm_resource=self.state.vm_ubuntu1, file_content="This file is in VM 1", value1=self.state.vm_ubuntu2.access_ip, value_list=["Test1", "Test2"])
        self.register_resource(self.state.vm_ubuntu1_configurator)

        # You can use values taken from other resources to configure a VM
        self.state.vm_ubuntu2_configurator = ExampleVmUbuntuConfigurator(vm_resource=self.state.vm_ubuntu2, file_content="This file is in VM 2", value1=self.state.vm_ubuntu1.access_ip, value_list=["Test1", "Test2"])
        self.register_resource(self.state.vm_ubuntu2_configurator)

        # The same need to be done to apply the configuration to the VMs
        self.provider.configure_vm(self.state.vm_ubuntu1_configurator)
        self.provider.configure_vm(self.state.vm_ubuntu2_configurator)

        # ################################# K8S Example #####################################

        # Define a new HelmChartResource, the chart can be directly passed as a compressed tgz, in this case set
        # chart_as_path to True
        # If you want to install a chart from a repo also set the 'repo' and 'version' fields
        self.state.mqtt_helm_chart = HelmChartResource(
            area=1,
            name=f"mqttbroker",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/mqttbroker-0.0.3.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.mqtt_helm_chart)
        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.mqtt_helm_chart,
            {
                "example_key": create_model.chart_value
            }
        )

    @classmethod
    def rest_create(cls, msg: ExampleCreateModel, request: Request):
        """
        This is needed for FastAPI to work, don't write code here, just changed the msg type to the correct one
        """
        return cls.api_day0_function(msg, request)
