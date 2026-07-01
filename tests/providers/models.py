from typing import Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.resources import NetResourcePool
from nfvcl_core_models.vim.vim_models import VimModel


class ProviderNetworkLifecycleConfig(NFVCLBaseModel):
    name: str = Field(description="Name of the network to create and delete on the VIM")
    cidr: str = Field(description="CIDR of the test network")
    allocation_pool: Optional[NetResourcePool] = Field(default=None)


class ProviderVimTestConfig(NFVCLBaseModel):
    vim: VimModel = Field(description="VIM model used to instantiate the provider directly")
    area: int = Field(description="Area resolved to this VIM during the test")
    resource_group: str = Field(default="provider_test")
    existing_networks: list[str] = Field(default_factory=list)
    missing_networks: list[str] = Field(default_factory=lambda: ["nfvcl-provider-test-missing-network"])
    create_network: Optional[ProviderNetworkLifecycleConfig] = Field(default=None)


class ProviderTestConfig(NFVCLBaseModel):
    vims: list[ProviderVimTestConfig] = Field(default_factory=list)
