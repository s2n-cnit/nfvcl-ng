from __future__ import annotations

import abc

from blueprints_ng.resources import VmResource, VmResourceConfiguration
from models.base_model import NFVCLBaseModel


class BlueprintNGProviderData(NFVCLBaseModel):
    pass


class BlueprintNGProviderInterface(abc.ABC):
    data: BlueprintNGProviderData

    @abc.abstractmethod
    def create_vm(self, vm_resource: VmResource):
        pass

    @abc.abstractmethod
    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration):
        pass

    @abc.abstractmethod
    def destroy_vm(self):
        pass

    @abc.abstractmethod
    def install_helm_chart(self):
        pass

    @abc.abstractmethod
    def update_values_helm_chart(self):
        pass

    @abc.abstractmethod
    def uninstall_helm_chart(self):
        pass
