from nfvcl_providers.virtualization.proxmox.virtualization_provider_proxmox import VirtualizationProviderProxmox

from nfvcl_providers.virtualization.openstack.virtualization_provider_openstack import VirtualizationProviderOpenstack

from nfvcl_core_models.vim.vim_models import VimTypeEnum

vim_type_to_provider_mapping = {
    VimTypeEnum.OPENSTACK: VirtualizationProviderOpenstack,
    VimTypeEnum.PROXMOX: VirtualizationProviderProxmox
}
