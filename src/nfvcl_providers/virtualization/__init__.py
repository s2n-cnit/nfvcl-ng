from nfvcl_providers.vim_clients.openstack_vim_client import OpenStackVimClient
from nfvcl_providers.vim_clients.proxmox_vim_client import ProxmoxVimClient
from nfvcl_providers.vim_clients.rest_vim_client import RESTVimClient
from nfvcl_providers.virtualization.external_rest.virtualization_provider_rest import VirtualizationProviderRest
from nfvcl_providers.virtualization.proxmox.virtualization_provider_proxmox import VirtualizationProviderProxmox

from nfvcl_providers.virtualization.openstack.virtualization_provider_openstack import VirtualizationProviderOpenstack

from nfvcl_core_models.vim.vim_models import VimTypeEnum

vim_type_to_provider_mapping = {
    VimTypeEnum.OPENSTACK: VirtualizationProviderOpenstack,
    VimTypeEnum.PROXMOX: VirtualizationProviderProxmox,
    VimTypeEnum.EXTERNAL_REST: VirtualizationProviderRest
}

vim_type_to_vim_client_mapping = {
    VimTypeEnum.OPENSTACK: OpenStackVimClient,
    VimTypeEnum.PROXMOX: ProxmoxVimClient,
    VimTypeEnum.EXTERNAL_REST: RESTVimClient
}
