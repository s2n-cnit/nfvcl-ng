from typing import List, Optional

from pydantic import Field

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel, BlueprintNGState
from nfvcl_core_models.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration, \
    HelmChartResource
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_common.utils.blue_utils import rel_path


class ExampleCreateModel(BlueprintNGCreateModel):
    """
    This class represent the model for the create request
    """
    area_id: int = Field()
    mgmt_net: str = Field()
    data_net: str = Field()
    chart_value: str = Field()


class ExampleAddVMModel(NFVCLBaseModel):
    """
    This class represent the model for add request
    """
    mgmt_net: str = Field()
    data_net: str = Field()
    num: int = Field()


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

    additional_vms: List[VmResource] = Field(default=[])
    additional_vms_configurators: List[ExampleVmUbuntuConfigurator] = Field(default=[])

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

        # This adds a task to gather a variable present in Ansible and return it to NFVCL
        ansible_builder.add_gather_var_task("kernel_version")

        # Add a simple task that run a command and return the output to NFVCL in a variable
        ansible_builder.add_run_command_and_gather_output_tasks("lsb_release -a", "ubuntu_version")

        # Build the playbook and return it
        return ansible_builder.build()


# This decorator is needed to declare a new blueprint type
# The blueprint class need to extend BlueprintNG, the type of the state and create model need to be explicitly passed
# for type hinting to work
@blueprint_type("example")
class ExampleBlueprintNG(BlueprintNG[ExampleBlueprintNGState, ExampleCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = ExampleBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: ExampleCreateModel):
        """
        This docstring for the create function will be shown on Swagger
        """
        super().create(create_model)
        self.logger.info("Starting creation of example blueprint")

        # ################################# VMs Example #####################################

        # To describe a new VM create a VmResource object and save it in the state
        self.state.vm_ubuntu1 = VmResource(
            area=create_model.area_id,
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
            area=create_model.area_id,
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
        ubuntu1_facts = self.provider.configure_vm(self.state.vm_ubuntu1_configurator)

        # ubuntu1_facts contains every fact present in the Ansible fact cache
        self.logger.warning(f"Ubuntu1 Kernel: {ubuntu1_facts['kernel_version']['stdout']}")
        self.logger.warning(f"Ubuntu1 Version: {ubuntu1_facts['ubuntu_version']}")

        self.provider.configure_vm(self.state.vm_ubuntu2_configurator)

        # ################################# K8S Example #####################################

        # Define a new HelmChartResource, the chart can be directly passed as a compressed tgz, in this case set
        # chart_as_path to True
        # If you want to install a chart from a repo also set the 'repo' and 'version' fields
        self.state.mqtt_helm_chart = HelmChartResource(
            area=create_model.area_id,
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

    @day2_function("/add_vm", [HttpRequestType.POST])
    def add_vm(self, model: ExampleAddVMModel):
        """
        This docstring for the add_vm day2 function will be shown on Swagger
        """
        new_vm = VmResource(
            area=self.create_config.area_id,
            name=f"{self.id}_VM_Ubuntu_{model.num}",
            image=VmResourceImage(name="ubuntu2204"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="ubuntu",
            management_network=model.mgmt_net,
            additional_networks=[model.data_net]
        )
        self.register_resource(new_vm)

        new_vm_configurator = ExampleVmUbuntuConfigurator(vm_resource=new_vm, file_content="This file is in VM 3", value1=self.state.vm_ubuntu1.access_ip, value_list=["TTest1", "TTest2"])
        self.register_resource(new_vm_configurator)

        self.state.additional_vms.append(new_vm)
        self.state.additional_vms_configurators.append(new_vm_configurator)

        self.provider.create_vm(new_vm)
        self.provider.configure_vm(new_vm_configurator)

    @day2_function("/get_vm", [HttpRequestType.GET])
    def get_vm(self) -> ExampleAddVMModel:
        """
        This docstring for the get_vm day2 function will be shown on Swagger
        """
        self.logger.info("get_vm function")
        return ExampleAddVMModel(mgmt_net="test", data_net="test", num=1)
