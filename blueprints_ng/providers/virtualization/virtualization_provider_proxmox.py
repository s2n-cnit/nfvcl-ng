from blueprints_ng.resources import VmResource, VmResourceConfiguration

from blueprints_ng.providers.virtualization.virtualization_provider_interface import VirtualizationProviderException, \
    VirtualizationProviderInterface, VirtualizationProviderData


class VirtualizationProviderDataProxmox(VirtualizationProviderData):
    pass


class VirtualizationProviderProxmoxException(VirtualizationProviderException):
    pass


class VirtualizationProviderProxmox(VirtualizationProviderInterface):
    def init(self):
        self.data: VirtualizationProviderDataProxmox = VirtualizationProviderDataProxmox()

    def create_vm(self, vm_resource: VmResource):
        pass

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        pass

    def destroy_vm(self, vm_resource: VmResource):
        pass

    def final_cleanup(self):
        pass
