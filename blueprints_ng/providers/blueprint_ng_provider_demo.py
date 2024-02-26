from blueprints_ng.providers.blueprint_ng_provider_interface import *
from blueprints_ng.resources import VmResourceAnsibleConfiguration, VmResourceNativeConfiguration, VmResourceNetworkInterfaceAddress, VmResourceNetworkInterface


class BlueprintNGProviderDataDemo(BlueprintNGProviderData):
    nsd: Dict[str, str] = {}
    vnf: Dict[str, str] = {}


class BlueprintsNgProviderDemo(BlueprintNGProviderInterface):

    def __init__(self):
        super().__init__()
        self.data: BlueprintNGProviderDataDemo = BlueprintNGProviderDataDemo()

    def create_vm(self, vm_resource: VmResource):
        print("create_vm begin")
        fixed = VmResourceNetworkInterfaceAddress(ip="10.0.0.1", mac="FF:FF:FF:FF:FF")
        floating = VmResourceNetworkInterfaceAddress(ip="192.168.0.1", mac="FF:FF:FF:FF:FF")
        vm_resource.network_interfaces["rete"] = VmResourceNetworkInterface(fixed=fixed, floating=floating)

        vm_resource.created = True

        self.data.nsd["IDNSD"] = vm_resource.id

        print("create_vm end")

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration):
        super().configure_vm(vm_resource_configuration)
        print("configure_vm begin")

        if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):
            dumped = vm_resource_configuration.dump_playbook()
            print(f"Sending dumped playbook to ansible: {dumped}")
        elif isinstance(vm_resource_configuration, VmResourceNativeConfiguration):
            print("Running the requested code")
            vm_resource_configuration.run_code()
            print("Finished running code")

        print("configure_vm end")

    def destroy_vm(self, vm_resource: VmResource):
        print("destroy_vm")

    def install_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        pass

    def update_values_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        pass

    def uninstall_helm_chart(self, helm_chart_resource: HelmChartResource):
        pass

    def configure_hardware(self, hardware_resource_configuration: HardwareResourceConfiguration):
        pass


