from __future__ import annotations

from collections.abc import Iterator, Mapping

from nfvcl_core_models.vim.vim_models import VimTypeEnum
from nfvcl_providers.virtualization.external_rest.virtualization_provider_rest import VirtualizationProviderRest
from nfvcl_providers.virtualization.openstack.virtualization_provider_openstack import VirtualizationProviderOpenstack
from nfvcl_providers.virtualization.proxmox.virtualization_provider_proxmox import VirtualizationProviderProxmox
from nfvcl_providers.virtualization.virtualization_provider_interface import VirtualizationProviderInterface


def get_virtualization_provider_class(vim_type: VimTypeEnum) -> type[VirtualizationProviderInterface]:
    match vim_type:
        case VimTypeEnum.OPENSTACK:
            return VirtualizationProviderOpenstack
        case VimTypeEnum.PROXMOX:
            return VirtualizationProviderProxmox
        case VimTypeEnum.EXTERNAL_REST:
            return VirtualizationProviderRest
        case _:
            raise KeyError(vim_type)


class VirtualizationProviderClassMapping(Mapping[VimTypeEnum, type[VirtualizationProviderInterface]]):
    _supported_vim_types = (
        VimTypeEnum.OPENSTACK,
        VimTypeEnum.PROXMOX,
        VimTypeEnum.EXTERNAL_REST,
    )

    def __getitem__(self, vim_type: VimTypeEnum) -> type[VirtualizationProviderInterface]:
        return get_virtualization_provider_class(vim_type)

    def __iter__(self) -> Iterator[VimTypeEnum]:
        return iter(self._supported_vim_types)

    def __len__(self) -> int:
        return len(self._supported_vim_types)


vim_type_to_provider_mapping = VirtualizationProviderClassMapping()
