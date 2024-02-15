from typing import Dict

from blueprints_ng.providers.blueprint_ng_provider_interface import *
from blueprints_ng.resources import VmResourceAnsibleConfiguration, VmResourceNativeConfiguration


class BlueprintNGProviderDataDemo(BlueprintNGProviderData):
    nsd: Dict[str, str] = {}
    vnf: Dict[str, str] = {}


class BlueprintsNgProviderDemo(BlueprintNGProviderInterface):

    def __init__(self):
        super().__init__()
        self.data: BlueprintNGProviderDataDemo = BlueprintNGProviderDataDemo()

    def create_vm(self, vm_resource: VmResource):
        print("create_vm begin")
        # Inviare a osm
        vm_resource.network_interfaces = {vm_resource.management_network: "1.1.1.1"}
        vm_resource.created = True

        self.data.nsd["IDNSD"] = vm_resource.id

        print("create_vm end")

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration):
        print("configure_vm begin")

        if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):
            dumped = vm_resource_configuration.dump_playbook()
            print(f"Sending dumped playbook to ansible: {dumped}")
        elif isinstance(vm_resource_configuration, VmResourceNativeConfiguration):
            print("Running the requested code")
            vm_resource_configuration.run_code()
            print("Finished running code")

        print("configure_vm end")

    def destroy_vm(self):
        print("destroy_vm")

    def install_helm_chart(self):
        print("install_helm_chart")

    def update_values_helm_chart(self):
        print("update_values_helm_chart")

    def uninstall_helm_chart(self):
        print("uninstall_helm_chart")
