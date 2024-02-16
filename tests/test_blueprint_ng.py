import gc
import random
import string
import unittest

from typing import Optional, List, Dict

from pydantic import Field

from blueprints_ng.blueprint_ng import BlueprintNGCreateModel, BlueprintNGState, BlueprintNG, get_class_path_str_from_obj
from blueprints_ng.providers.blueprint_ng_provider_native import BlueprintsNgProviderDemo, BlueprintNGProviderDataDemo

from blueprints_ng.resources import VmResourceAnsibleConfiguration, VmResourceNativeConfiguration, VmResource, VmResourceImage, VmResourceFlavor, VmResourceConfiguration
from models.base_model import NFVCLBaseModel


class TestCreateModel(BlueprintNGCreateModel):
    var1: str = Field()
    var2: str = Field()


class TestUbuntuVmResourceConfiguration(VmResourceAnsibleConfiguration):
    def build_configuration(self, configuration_values: TestCreateModel):
        pass

    def dump_playbook(self) -> str:
        return super().dump_playbook()


class TestFedoraVmResourceConfiguration(VmResourceNativeConfiguration):
    max_num: int = Field(default=10)

    def run_code(self):
        print(f"###Configuro la macchina ubuntu con IP {self.vm_resource.network_interfaces[self.vm_resource.management_network]}, max_num={self.max_num}")

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

    additional_areas: List[TestStateResourceWrapper] = Field(default_factory=list)

    container_list: Optional[List[TestStateResourcesContainer]] = Field(default=None)


class TestBlueprintNG(BlueprintNG[TestBlueprintNGState, BlueprintNGProviderDataDemo, TestCreateModel]):
    def create(self, create: TestCreateModel):
        super().create(create)
        self.state.vm_ubuntu = VmResource(
            area=0,
            name="VM Ubuntu",
            image=VmResourceImage(name="ubuntu2204"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="root",
            management_network="dmz-internal",
            additional_networks=["data-net"]
        )

        self.state.vm_fedora = VmResource(
            area=0,
            name="VM Fedora",
            image=VmResourceImage(name="fedora"),
            flavor=VmResourceFlavor(),
            username="fedora",
            password="root",
            management_network="dmz-internal",
            additional_networks=["data-net"]
        )

        self.state.vm_ubuntu_configurator = TestUbuntuVmResourceConfiguration(vm_resource=self.state.vm_ubuntu)
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

    def add_area(self):
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


unittest.TestLoader.sortTestMethodsUsing = lambda self, a, b: (a > b) - (a < b)


def get_vm_resources_from_memory():
    objects_in_interpreter = gc.get_objects()
    objects_in_interpreter_filtered = list(filter(lambda x: isinstance(x, VmResource), objects_in_interpreter))
    return objects_in_interpreter_filtered


def random_string(length):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


class UnitTestBlueprintNG(unittest.TestCase):
    blue_instance = None
    serialized_shared = None
    recreated_instance_shared = None

    @property
    def serialized(self):
        return self.__class__.serialized_shared

    @serialized.setter
    def serialized(self, value):
        self.__class__.serialized_shared = value

    @property
    def recreated_instance(self):
        return self.__class__.recreated_instance_shared

    @recreated_instance.setter
    def recreated_instance(self, value):
        self.__class__.recreated_instance_shared = value

    @classmethod
    def setUpClass(cls):
        cls.blue_instance = TestBlueprintNG(BlueprintsNgProviderDemo, TestBlueprintNGState)

    @classmethod
    def tearDownClass(cls):
        cls.blue_instance = None

    def test_000_initial_state(self):
        # No resource have to be registered on init
        self.assertEqual(len(self.blue_instance.base_model.registered_resources), 0)
        # The state need to be empty
        self.assertEqual(self.blue_instance.base_model.state, TestBlueprintNGState())

    def test_001_creation(self):
        self.random_var1 = random_string(10)
        self.random_var2 = random_string(10)

        create_config = TestCreateModel(var1=self.random_var1, var2=self.random_var2)

        self.blue_instance.create(create_config)
        self.assertEqual(len(self.blue_instance.base_model.registered_resources), 4)
        self.assertEqual(self.blue_instance.create_config, create_config)
        self.assertEqual(self.blue_instance.base_model.create_config_type, get_class_path_str_from_obj(create_config))

    def check_state_after_creation(self, instance: TestBlueprintNG):
        self.assertIsNotNone(instance.state.vm_ubuntu)
        self.assertIsNotNone(instance.state.vm_ubuntu_configurator)
        self.assertIsNotNone(instance.state.vm_fedora)
        self.assertIsNotNone(instance.state.vm_fedora_configurator)

        self.assertEqual(instance.state.vm_ubuntu_configurator.vm_resource, instance.state.vm_ubuntu)
        self.assertEqual(id(instance.state.vm_ubuntu_configurator.vm_resource), id(instance.state.vm_ubuntu))
        self.assertEqual(instance.state.vm_fedora_configurator.vm_resource, instance.state.vm_fedora)
        self.assertEqual(id(instance.state.vm_fedora_configurator.vm_resource), id(instance.state.vm_fedora))

        self.assertNotEqual(instance.state.vm_ubuntu, instance.state.vm_fedora)
        self.assertNotEqual(instance.state.vm_ubuntu_configurator, instance.state.vm_fedora_configurator)

        self.assertEqual(instance.state.vm_fedora_configurator.max_num, 12)

    def test_002_state_after_creation(self):
        self.check_state_after_creation(self.blue_instance)

    def test_003_serialize(self):
        self.serialized = self.blue_instance.to_db()
        print(self.serialized)
        self.assertEqual(15, self.serialized.count("REF="))

    def test_004_deserialize(self):
        self.recreated_instance = TestBlueprintNG(BlueprintsNgProviderDemo, TestBlueprintNGState)
        self.recreated_instance.from_db(self.serialized)

    def test_005_deserialized_integrity_check(self):
        self.check_state_after_creation(self.recreated_instance)

    def test_006_add_area(self):
        self.recreated_instance.add_area()
        self.assertEqual(len(self.recreated_instance.base_model.registered_resources), 6)
        self.assertEqual(self.recreated_instance.state.vm_fedora_configurator.max_num, 2)

    def test_007_serialize_after_area(self):
        serialized = self.recreated_instance.to_db()
        print(self.serialized)
        self.assertEqual(18, serialized.count("REF="))

    def test_999_check_memory_instances(self):
        # There should be 5 object in memory here:
        # self.blue_instance: 2
        # self.recreated_instance: 2 + 1 (new area)
        self.assertEqual(5, len(get_vm_resources_from_memory()))

        # Delete the object from memory
        del self.blue_instance.base_model
        gc.collect()

        # There should be 3 object in memory here:
        # self.recreated_instance: 2 + 1 (new area)
        self.assertEqual(3, len(get_vm_resources_from_memory()))


if __name__ == '__main__':
    unittest.main()
