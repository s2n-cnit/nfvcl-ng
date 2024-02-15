from typing import List, Optional, Dict

from pydantic import Field

from blueprints_ng.blueprint_ng_provider_interface import VmResource, VmResourceImage, VmResourceFlavor, \
    BlueprintNGCreateModel, BlueprintNG, VmResourceAnsibleConfiguration, VmResourceNativeConfiguration, BlueprintNGState
from blueprints_ng.blueprint_ng_provider_native import BlueprintsNgProviderDemo, BlueprintNGProviderDataDemo
from models.base_model import NFVCLBaseModel


class DemoCreateModel(BlueprintNGCreateModel):
    var: str = Field()


class UbuntuVmResourceConfiguration(VmResourceAnsibleConfiguration):
    def build_configuration(self, configuration_values: DemoCreateModel):
        pass

    def dump_playbook(self) -> str:
        return super().dump_playbook()


class FedoraVmResourceConfiguration(VmResourceNativeConfiguration):
    max_num: int = Field(default=10)

    def run_code(self):
        print(f"###Configuro la macchina ubuntu con IP {self.vm_resource.network_interfaces[self.vm_resource.management_network]}, max_num={self.max_num}")

        for i in range(1, self.max_num):
            print(i)

class Pippo(NFVCLBaseModel):
    vm1: Optional[VmResource] = Field(default=None)
    vmddd: Dict[str, VmResource] = Field(default={})
    vmlll: List[VmResource] = Field(default={})

class DemoBlueprintNGState(BlueprintNGState):
    areas: List[str] = Field(default_factory=list)
    core_vm: Optional[VmResource] = Field(default=None)
    vm_fedora: Optional[VmResource] = Field(default=None)
    vm_fedora_configurator: Optional[FedoraVmResourceConfiguration] = Field(default=None)
    prova_lista: Optional[List[Pippo]] = Field(default=None)

class NGDemoBlueprint(BlueprintNG[DemoBlueprintNGState, BlueprintNGProviderDataDemo, DemoCreateModel]):
    def create(self, create_model: DemoCreateModel):
        vm_ubuntu = VmResource(
            area="0",
            name="VM Ubuntu",
            image=VmResourceImage(name="ubuntu2204"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="root",
            management_network="dmz-internal",
            additional_networks=["alderico-net"]
        )

        self.state.vm_fedora = VmResource(
            area="0",
            name="VM Fedora",
            image=VmResourceImage(name="fedora"),
            flavor=VmResourceFlavor(),
            username="fedora",
            password="root",
            management_network="dmz-internal",
            additional_networks=["alderico-net"]
        )

        self.state.areas.append("1")
        self.state.areas.append("2")
        self.state.areas.append("3")
        self.state.areas.append("4")

        vm_ubuntu_configurator = UbuntuVmResourceConfiguration(vm_resource=vm_ubuntu)
        self.state.vm_fedora_configurator = FedoraVmResourceConfiguration(vm_resource=self.state.vm_fedora, max_num=12)

        self.register_resource(vm_ubuntu)
        self.register_resource(self.state.vm_fedora)
        self.register_resource(vm_ubuntu_configurator)
        self.register_resource(self.state.vm_fedora_configurator)

        vm_ubuntu.create()
        self.state.vm_fedora.create()


        vm_ubuntu_configurator.configure()
        self.state.vm_fedora_configurator.configure()

        self.state.prova_lista = [
            Pippo(
                vm1=vm_ubuntu,
                vmddd={"CIAO": self.state.vm_fedora},
                vmlll=[vm_ubuntu, self.state.vm_fedora]
            ),
            Pippo(
                vm1=vm_ubuntu,
                vmddd={"CIAO": self.state.vm_fedora, "paperino": vm_ubuntu},
                vmlll=[vm_ubuntu, self.state.vm_fedora]
            )
        ]

    def add_area(self):
        new_vm = VmResource(
            area="1",
            name="VM Fedora in area 1",
            image=VmResourceImage(name="fedora"),
            flavor=VmResourceFlavor(),
            username="fedora",
            password="root",
            management_network="dmz-internal",
            additional_networks=["alderico-net"]
        )

        new_vm_configurator = FedoraVmResourceConfiguration(vm_resource=new_vm, max_num=4)

        self.register_resource(new_vm)
        self.register_resource(new_vm_configurator)

        new_vm.create()

        self.state.vm_fedora_configurator.max_num = 2
        self.state.vm_fedora_configurator.configure()

        # new_vm_configurator.configure()



if __name__ == "__main__":
    prova = NGDemoBlueprint(BlueprintsNgProviderDemo, DemoBlueprintNGState)
    prova.create(DemoCreateModel(var="CIAOOOO"))
    serializzato = prova.to_db()
    print(serializzato)

    reistanza = NGDemoBlueprint(BlueprintsNgProviderDemo, DemoBlueprintNGState)

    reistanza.from_db(serializzato)
    print(reistanza.state.vm_fedora_configurator.vm_resource)
    print(reistanza.state.vm_fedora)

    serializzato2 = reistanza.to_db()
    import gc
    del prova

    collected = gc.collect()

    # Prints Garbage collector
    # as 0 object
    print("Garbage collector: collected",
          "%d objects." % collected)

    print(f"UGUALI: {serializzato == serializzato2}")

    test = gc.get_objects()
    test_filtered = list(filter(lambda x: isinstance(x, VmResource), test))
    assert id(reistanza.state.vm_fedora) == id(reistanza.state.vm_fedora_configurator.vm_resource)
    reistanza.add_area()
    assert id(reistanza.state.vm_fedora) == id(reistanza.state.vm_fedora_configurator.vm_resource)


