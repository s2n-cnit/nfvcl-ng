import pytest

from nfvcl_core_models.resources import NetResource
from tests.providers.models import ProviderTestConfig


pytestmark = pytest.mark.provider_vim


def test_configured_real_vims_can_check_networks(
    provider_test_config: ProviderTestConfig,
    real_vim_provider_factory,
):
    assert provider_test_config.vims, "provider config must define at least one VIM"

    for vim_case in provider_test_config.vims:
        provider = real_vim_provider_factory(vim_case)
        networks_to_check = set(vim_case.existing_networks) | set(vim_case.missing_networks)

        ok, missing_networks = provider.check_networks_exist_on_vim(
            vim_case.area,
            networks_to_check,
            resource_group=vim_case.resource_group,
        )

        assert set(vim_case.existing_networks).isdisjoint(missing_networks)
        assert set(vim_case.missing_networks).issubset(missing_networks)
        assert ok is (len(missing_networks) == 0)


@pytest.mark.provider_destructive
def test_configured_real_vims_can_create_and_cleanup_networks(
    provider_test_config: ProviderTestConfig,
    real_vim_provider_factory,
):
    configured_cases = [vim_case for vim_case in provider_test_config.vims if vim_case.create_network is not None]
    if not configured_cases:
        pytest.skip("no create_network entries configured")

    for vim_case in configured_cases:
        provider = real_vim_provider_factory(vim_case)
        network_config = vim_case.create_network
        network = NetResource(
            resource_group=vim_case.resource_group,
            area=vim_case.area,
            name=network_config.name,
            cidr=network_config.cidr,
            allocation_pool=network_config.allocation_pool,
        )

        try:
            provider.create_net(network)
            ok, missing_networks = provider.check_networks_exist_on_vim(
                vim_case.area,
                {network.name},
                resource_group=vim_case.resource_group,
            )
            assert ok is True
            assert network.name not in missing_networks
        finally:
            provider.cleanup_resource_group(vim_case.resource_group)
