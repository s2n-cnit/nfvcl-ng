from typing import Optional, Dict, List

from fastapi import Request
from pydantic import Field

from blueprints_ng.ansible_builder import AnsiblePlaybookBuilder
from blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGCreateModel, BlueprintNGState
from blueprints_ng.lcm.blueprint_route_manager import add_route
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.providers.blueprint_ng_provider_demo import BlueprintNGProviderDataDemo
from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface
from blueprints_ng.resources import VmResource, VmResourceFlavor, VmResourceImage, VmResourceAnsibleConfiguration, \
    VmResourceNativeConfiguration, VmResourceConfiguration, HelmChartResource
from blueprints_ng.utils import rel_path
from models.base_model import NFVCLBaseModel
from models.http_models import HttpRequestType


class TestCreateModel(BlueprintNGCreateModel):
    var1: str = Field()
    var2: str = Field()


class TestDay2Model(BlueprintNGCreateModel):
    var2: str = Field()
    var3: str = Field()
    test: int = Field(description="Indicates the number of the test")


class TestUbuntuVmResourceConfiguration(VmResourceAnsibleConfiguration):
    file_content: str = Field(default="")

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook UbuntuVmResourceConfiguration")
        ansible_builder.add_tasks_from_file(rel_path("play.yaml"))

        ansible_builder.set_var("file_content", self.file_content)
        ansible_builder.set_var("lb_ipaddresses", ["ADDR1", ["ADDR2"]])
        ansible_builder.set_var("lb_pools", "ESEEEEE")

        ansible_builder.add_template_task(rel_path("conffile.jinja2"), "/confffff")

        print("#####################################")
        print(f"{ansible_builder.build()}")
        print("#####################################")
        return ansible_builder.build()


class TestFedoraVmResourceConfiguration(VmResourceNativeConfiguration):
    max_num: int = Field(default=10)

    def run_code(self):
        for i in range(1, self.max_num):
            print(i)


class TestStateResourcesContainer(NFVCLBaseModel):
    normal: Optional[VmResource] = Field(default=None)
    dictionary: Dict[str, VmResource] = Field(default={})
    list: List[VmResource] = Field(default={})


class TestStateResourceWrapper(NFVCLBaseModel):
    resource: Optional[VmResource] = Field(default=None)
    configurator: Optional[VmResourceConfiguration] = Field(default=None)


class TestBlueprintNGState(BlueprintNGState):
    areas: List[str] = Field(default_factory=list)

    core_vm: Optional[VmResource] = Field(default=None)
    vm_fedora: Optional[VmResource] = Field(default=None)
    vm_fedora_configurator: Optional[TestFedoraVmResourceConfiguration] = Field(default=None)
    vm_ubuntu: Optional[VmResource] = Field(default=None)
    vm_ubuntu_configurator: Optional[TestUbuntuVmResourceConfiguration] = Field(default=None)

    helm_chart: Optional[HelmChartResource] = Field(default=None)

    additional_areas: List[TestStateResourceWrapper] = Field(default_factory=list)

    container_list: Optional[List[TestStateResourcesContainer]] = Field(default=None)


VYOS_BLUE_TYPE = "vyos"


@declare_blue_type(VYOS_BLUE_TYPE)
class VyosBlueprintNG(BlueprintNG[TestBlueprintNGState, TestCreateModel]):
    def __init__(self, blueprint_id: str, provider_type: type[BlueprintNGProviderInterface], state_type: type[BlueprintNGState] = TestBlueprintNGState):
        super().__init__(blueprint_id, provider_type, state_type)

    def create(self, create: TestCreateModel):
        self.logger.info("Createeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")

        super().create(create)


        self.state.helm_chart = HelmChartResource(
            area=1,
            name=f"prova",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/mqttbroker-0.0.3.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.provider.install_helm_chart(self.state.helm_chart, {})

        self.register_resource(self.state.helm_chart)

        self.state.vm_ubuntu = VmResource(
            area=0,
            name="VM Ubuntu",
            image=VmResourceImage(name="ubuntu2204"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="ubuntu",
            management_network="dmz-internal",
            additional_networks=["alderico-net"]
        )

        self.state.vm_fedora = VmResource(
            area=0,
            name="VM Fedora",
            image=VmResourceImage(name="ubuntu2204"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="ubuntu",
            management_network="dmz-internal",
            additional_networks=["alderico-net"]
        )

        self.state.vm_ubuntu_configurator = TestUbuntuVmResourceConfiguration(vm_resource=self.state.vm_ubuntu, file_content="OOOOOOOOOOOOO")
        self.state.vm_fedora_configurator = TestFedoraVmResourceConfiguration(vm_resource=self.state.vm_fedora, max_num=12)

        self.register_resource(self.state.vm_ubuntu)
        self.register_resource(self.state.vm_fedora)
        self.register_resource(self.state.vm_ubuntu_configurator)
        self.register_resource(self.state.vm_fedora_configurator)

        self.provider.create_vm(self.state.vm_ubuntu)
        self.provider.create_vm(self.state.vm_fedora)
        self.provider.configure_vm(self.state.vm_ubuntu_configurator)
        self.provider.configure_vm(self.state.vm_fedora_configurator)

        self.state.container_list = [
            TestStateResourcesContainer(
                normal=self.state.vm_ubuntu,
                dictionary={"KEY": self.state.vm_fedora},
                list=[self.state.vm_ubuntu, self.state.vm_fedora]
            ),
            TestStateResourcesContainer(
                normal=self.state.vm_ubuntu,
                dictionary={"KEY1": self.state.vm_fedora, "KEY2": self.state.vm_ubuntu},
                list=[self.state.vm_ubuntu, self.state.vm_fedora]
            )
        ]
        self.to_db()

    @classmethod
    def rest_create(cls, msg: TestCreateModel, request: Request):
        return cls.api_day0_function(msg, request)

    @classmethod
    def add_area_endpoint(cls, msg: TestCreateModel, blue_id: str, request: Request):
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(VYOS_BLUE_TYPE, "/test_api_path", [HttpRequestType.POST], add_area_endpoint)
    def add_area(self, msg):
        new_vm = VmResource(
            area=1,
            name="VM Fedora in area 1",
            image=VmResourceImage(name="fedora"),
            flavor=VmResourceFlavor(),
            username="fedora",
            password="root",
            management_network="dmz-internal",
            additional_networks=["alderico-net"]
        )

        new_vm_configurator = TestFedoraVmResourceConfiguration(vm_resource=new_vm, max_num=4)

        self.register_resource(new_vm)
        self.register_resource(new_vm_configurator)

        self.state.additional_areas.append(TestStateResourceWrapper(resource=new_vm, configurator=new_vm_configurator))

        self.provider.create_vm(new_vm)

        self.state.vm_fedora_configurator.max_num = 2

        self.provider.configure_vm(self.state.vm_fedora_configurator)
        self.provider.configure_vm(new_vm_configurator)
        self.to_db()

    @classmethod
    def add_area3234_endpoint(cls, msg: TestDay2Model, blue_id: str, request: Request):
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(VYOS_BLUE_TYPE, "/test_api_path3234", [HttpRequestType.POST], add_area3234_endpoint)
    def add_area3234(self, msg):
        new_vm = VmResource(
            area=1,
            name="VM Fedora in area 1",
            image=VmResourceImage(name="fedora"),
            flavor=VmResourceFlavor(),
            username="fedora",
            password="root",
            management_network="dmz-internal",
            additional_networks=["alderico-net"]
        )

        new_vm_configurator = TestFedoraVmResourceConfiguration(vm_resource=new_vm, max_num=4)

        self.register_resource(new_vm)
        self.register_resource(new_vm_configurator)
        self.provider.create_vm(new_vm)

        self.logger.info("add_area3234 day 2 has finished correctly.")

        self.to_db()
