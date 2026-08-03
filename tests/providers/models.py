from typing import Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.resources import NetResourcePool, VmResourceFlavor, VmResourceImage
from nfvcl_core_models.vim.vim_models import VimModel


class ProviderNetworkLifecycleConfig(NFVCLBaseModel):
    name: str = Field(description="Name of the network to create and delete on the VIM")
    cidr: str = Field(description="CIDR of the test network")
    allocation_pool: Optional[NetResourcePool] = Field(default=None)


class ProviderVmLifecycleConfig(NFVCLBaseModel):
    name: str = Field(description="Name of the VM to create and delete on the VIM")
    image: VmResourceImage = Field(description="Image used to create the test VM")
    flavor: VmResourceFlavor = Field(default_factory=VmResourceFlavor)
    username: str = Field(description="Username used by Ansible/SSH to configure the test VM")
    password: str = Field(description="Password used by Ansible/SSH to configure the test VM")
    become_password: Optional[str] = Field(default=None)
    management_network: str = Field(description="Existing management network used to create the test VM")
    attach_network: ProviderNetworkLifecycleConfig = Field(description="Network created and attached during the lifecycle test")
    require_floating_ip: bool = Field(default=False)
    require_port_security_disabled: Optional[bool] = Field(default=False)
    hard_reboot: bool = Field(default=False)


class ProviderVimTestConfig(NFVCLBaseModel):
    vim: VimModel = Field(description="VIM model used to instantiate the provider directly")
    area: int = Field(description="Area resolved to this VIM during the test")
    resource_group: str = Field(default="provider_test")
    existing_networks: list[str] = Field(default_factory=list)
    missing_networks: list[str] = Field(default_factory=lambda: ["nfvcl-provider-test-missing-network"])
    create_network: Optional[ProviderNetworkLifecycleConfig] = Field(default=None)
    vm_lifecycle: Optional[ProviderVmLifecycleConfig] = Field(default=None)


class ProviderTestConfig(NFVCLBaseModel):
    vims: list[ProviderVimTestConfig] = Field(default_factory=list)
