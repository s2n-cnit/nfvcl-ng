from pathlib import Path
from typing import Iterator

import pytest

from nfvcl_common.utils.blue_utils import get_yaml_parser
from nfvcl_core_models.vim.vim_models import VimModel
from nfvcl_providers.vim_clients.vim_client import VimClient
from nfvcl_providers.vim_clients.vim_context import VimClientPool
from nfvcl_providers.virtualization import get_virtualization_provider_class
from nfvcl_providers.virtualization.virtualization_provider_interface import VirtualizationProviderInterface
from tests.providers.models import ProviderTestConfig, ProviderVimTestConfig


class StaticVimResolver:
    def __init__(self, vims: list[VimModel]):
        self.vims_by_area = {
            area: vim
            for vim in vims
            for area in vim.areas
        }
        self.vims_by_name = {
            vim.name: vim
            for vim in vims
        }

    def get_vim_by_area(self, area: int) -> VimModel:
        return self.vims_by_area[area]

    def get_vim_by_name(self, vim_name: str) -> VimModel:
        return self.vims_by_name[vim_name]


@pytest.fixture(scope="session")
def provider_test_config(pytestconfig: pytest.Config) -> ProviderTestConfig:
    config_path = pytestconfig.getoption("--provider-config")
    if not config_path:
        pytest.skip("provider VIM tests require --provider-config")

    path = Path(config_path)
    if not path.is_file():
        pytest.skip(f"provider config file not found: {path}")

    parser = get_yaml_parser()
    with path.open("r") as config_file:
        config = parser.load(config_file)
    return ProviderTestConfig.model_validate(config)


def build_real_vim_provider(
    vim_case: ProviderVimTestConfig,
) -> tuple[VirtualizationProviderInterface, VimClientPool]:
    provider_class = get_virtualization_provider_class(vim_case.vim.vim_type)
    pool = VimClientPool(StaticVimResolver([vim_case.vim]))
    provider = provider_class(vim_client_pool=pool)
    return provider, pool


@pytest.fixture
def real_vim_provider_factory() -> Iterator:
    pools: list[VimClientPool] = []

    def factory(vim_case: ProviderVimTestConfig) -> VirtualizationProviderInterface:
        provider, pool = build_real_vim_provider(vim_case)
        pools.append(pool)
        return provider

    yield factory

    for pool in pools:
        pool.close()
