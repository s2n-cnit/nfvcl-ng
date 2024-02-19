from typing import Optional, List, Dict

from pydantic import Field

from blueprints_ng.blueprint_ng import BlueprintNGCreateModel, BlueprintNGState, BlueprintNG
from blueprints_ng.providers.blueprint_ng_provider_demo import BlueprintsNgProviderDemo, BlueprintNGProviderDataDemo
from blueprints_ng.providers.blueprint_ng_provider_native import BlueprintsNgProviderNative

from blueprints_ng.resources import VmResourceAnsibleConfiguration, VmResourceNativeConfiguration, VmResource, VmResourceImage, VmResourceFlavor
from models.base_model import NFVCLBaseModel


class DemoCreateModel(BlueprintNGCreateModel):
    var: str = Field()


class UbuntuVmResourceConfiguration(VmResourceAnsibleConfiguration):
    file_content: str = Field(default="")
    def build_configuration(self, configuration_values: DemoCreateModel):
        return f"""
- hosts: all
  tasks:
    - name: Writing file
      shell: |
        echo '{self.file_content}' > /home/ubuntu/fileprova
"""

    def dump_playbook(self) -> str:
        return f"""
- hosts: all
  tasks:
    - name: Writing file
      shell: |
        echo '{self.file_content}' > /home/ubuntu/fileprova
"""


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
    vm_ubuntu: Optional[VmResource] = Field(default=None)
    vm_fedora: Optional[VmResource] = Field(default=None)
    vm_fedora_configurator: Optional[FedoraVmResourceConfiguration] = Field(default=None)
    vm_ubuntu_configurator: Optional[UbuntuVmResourceConfiguration] = Field(default=None)
    prova_lista: Optional[List[Pippo]] = Field(default=None)


class NGDemoBlueprint(BlueprintNG[DemoBlueprintNGState, BlueprintNGProviderDataDemo, DemoCreateModel]):
    def create(self, create_model: DemoCreateModel):
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
            image=VmResourceImage(name="Fedora38"),
            flavor=VmResourceFlavor(),
            username="fedora",
            password="root",
            management_network="dmz-internal",
            require_floating_ip=True
            # additional_networks=["alderico-net"]
        )

        self.state.areas.append("1")
        self.state.areas.append("2")
        self.state.areas.append("3")
        self.state.areas.append("4")

        self.state.vm_ubuntu_configurator = UbuntuVmResourceConfiguration(vm_resource=self.state.vm_ubuntu, file_content="CIAOAOOOO")
        self.state.vm_fedora_configurator = FedoraVmResourceConfiguration(vm_resource=self.state.vm_fedora, max_num=12)

        self.register_resource(self.state.vm_ubuntu)
        self.register_resource(self.state.vm_fedora)
        self.register_resource(self.state.vm_ubuntu_configurator)
        self.register_resource(self.state.vm_fedora_configurator)

        self.provider.create_vm(self.state.vm_ubuntu)
        self.provider.create_vm(self.state.vm_fedora)
        self.provider.configure_vm(self.state.vm_ubuntu_configurator)
        self.provider.configure_vm(self.state.vm_fedora_configurator)

        self.state.prova_lista = [
            Pippo(
                vm1=self.state.vm_ubuntu,
                vmddd={"CIAO": self.state.vm_fedora},
                vmlll=[self.state.vm_ubuntu, self.state.vm_fedora]
            ),
            Pippo(
                vm1=self.state.vm_ubuntu,
                vmddd={"CIAO": self.state.vm_fedora, "paperino": self.state.vm_ubuntu},
                vmlll=[self.state.vm_ubuntu, self.state.vm_fedora]
            )
        ]

    def add_area(self):
        new_vm = VmResource(
            area=1,
            name="VM Fedora in area 1",
            image=VmResourceImage(name="Fedora38"),
            flavor=VmResourceFlavor(),
            username="fedora",
            password="root",
            management_network="dmz-internal",
            additional_networks=["alderico-net"]
        )

        new_vm_configurator = FedoraVmResourceConfiguration(vm_resource=new_vm, max_num=4)

        self.register_resource(new_vm)
        self.register_resource(new_vm_configurator)

        self.provider.create_vm(new_vm)

        self.state.vm_fedora_configurator.max_num = 2
        self.provider.configure_vm(self.state.vm_fedora_configurator)

    def change_file_content_ubuntu(self):
        self.state.vm_ubuntu_configurator.file_content = self.state.vm_fedora.access_ip
        self.provider.configure_vm(self.state.vm_ubuntu_configurator)


if __name__ == "__main__":
    prova = NGDemoBlueprint(BlueprintsNgProviderNative, DemoBlueprintNGState)
    prova.create(DemoCreateModel(var="CIAOOOO"))
    serializzato = prova.to_db()
    print(serializzato)
    reistanza = NGDemoBlueprint.from_db(serializzato)
    reistanza.add_area()
    reistanza.change_file_content_ubuntu()
    print("PAUSA")
    reistanza.destroy()
    # prova.destroy()
    print("PAUSA2")
