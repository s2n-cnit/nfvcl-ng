from typing import Dict, Optional

from pydantic import Field, SerializeAsAny

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.resources import VmResource, NetResource
from nfvcl_providers.virtualization.virtualization_provider_interface import VirtualizationProviderData


class NFVCLProviderResourceGroup(NFVCLBaseModel):
    id: str = Field()
    provider_data: Optional[Dict[str, SerializeAsAny[VirtualizationProviderData]]] = Field(default_factory=dict)
    vm_resources: Optional[Dict[str, VmResource]] = Field(default_factory=dict)
    net_resources: Optional[Dict[str, NetResource]] = Field(default_factory=dict)

class NFVCLProviderAgent(NFVCLBaseModel):
    uuid: str = Field()
    resource_groups: Optional[Dict[str, NFVCLProviderResourceGroup]] = Field(default_factory=dict)
