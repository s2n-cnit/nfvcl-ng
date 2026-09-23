from __future__ import annotations

from collections.abc import Iterator, Mapping

from nfvcl_core_models.vim.vim_models import VimTypeEnum
from nfvcl_providers.containerization.containerization_provider_interface import ContainerizationProviderInterface
from nfvcl_providers.containerization.incus.container_provider_incus import ContainerProviderIncus


def get_containerization_provider_class(vim_type: VimTypeEnum) -> type[ContainerizationProviderInterface]:
    match vim_type:
        case VimTypeEnum.INCUS:
            return ContainerProviderIncus
        case _:
            raise KeyError(vim_type)


class ContainerizationProviderClassMapping(Mapping[VimTypeEnum, type[ContainerizationProviderInterface]]):
    _supported_vim_types = (
        VimTypeEnum.INCUS,
    )

    def __getitem__(self, vim_type: VimTypeEnum) -> type[ContainerizationProviderInterface]:
        return get_containerization_provider_class(vim_type)

    def __iter__(self) -> Iterator[VimTypeEnum]:
        return iter(self._supported_vim_types)

    def __len__(self) -> int:
        return len(self._supported_vim_types)


vim_type_to_containerization_provider_mapping = ContainerizationProviderClassMapping()
