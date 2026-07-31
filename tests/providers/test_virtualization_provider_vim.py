from contextlib import suppress
import time

import pytest

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_core_models.resources import (
    NetResource,
    VmPowerStatus,
    VmResource,
    VmResourceAnsibleConfiguration,
    VmStatus,
)
from nfvcl_providers.virtualization.virtualization_provider_interface import VirtualizationProviderInterface
from tests.providers.models import (
    ProviderNetworkLifecycleConfig,
    ProviderTestConfig,
    ProviderVimTestConfig,
    ProviderVmLifecycleConfig,
)


pytestmark = pytest.mark.provider_vim

VM_STATUS_TIMEOUT_SECONDS = 300
VM_STATUS_POLL_SECONDS = 10
CONFIGURE_FACT_NAME = "provider_lifecycle"
CONFIGURE_FACT_VALUE = "nfvcl-provider-lifecycle"


class ProviderLifecycleConfigurator(VmResourceAnsibleConfiguration):
    def dump_playbook(self) -> str:
        builder = AnsiblePlaybookBuilder("Provider lifecycle smoke", become=False)
        builder.add_run_command_and_gather_output_tasks(
            f"printf {CONFIGURE_FACT_VALUE}",
            CONFIGURE_FACT_NAME,
        )
        return builder.build()


def _power_status_value(status: VmPowerStatus | str) -> str:
    return status.value if hasattr(status, "value") else status


def _build_net_resource(
    vim_case: ProviderVimTestConfig,
    network_config: ProviderNetworkLifecycleConfig,
) -> NetResource:
    return NetResource(
        resource_group=vim_case.resource_group,
        area=vim_case.area,
        name=network_config.name,
        cidr=network_config.cidr,
        allocation_pool=network_config.allocation_pool,
    )


def _build_vm_resource(
    vim_case: ProviderVimTestConfig,
    vm_config: ProviderVmLifecycleConfig,
) -> VmResource:
    return VmResource(
        id=f"{vim_case.resource_group}-{vm_config.name}",
        resource_group=vim_case.resource_group,
        area=vim_case.area,
        name=vm_config.name,
        image=vm_config.image,
        flavor=vm_config.flavor,
        username=vm_config.username,
        password=vm_config.password,
        become_password=vm_config.become_password,
        management_network=vm_config.management_network,
        require_floating_ip=vm_config.require_floating_ip,
        require_port_security_disabled=vm_config.require_port_security_disabled,
    )


def _assert_vm_running(status: VmStatus, vm_resource: VmResource) -> None:
    assert status.vm_name == vm_resource.name
    assert _power_status_value(status.power_status) == VmPowerStatus.RUNNING.value


def _wait_for_vm_running(
    provider: VirtualizationProviderInterface,
    vm_resource: VmResource,
) -> VmStatus:
    deadline = time.monotonic() + VM_STATUS_TIMEOUT_SECONDS
    last_status: VmStatus | None = None
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            last_status = provider.check_vm_status(vm_resource)
            last_error = None
        except Exception as exc:
            last_error = exc
        else:
            if _power_status_value(last_status.power_status) == VmPowerStatus.RUNNING.value:
                return last_status
        time.sleep(VM_STATUS_POLL_SECONDS)

    pytest.fail(
        f"VM {vm_resource.name} did not reach {VmPowerStatus.RUNNING.value}; "
        f"last_status={last_status}, last_error={last_error}"
    )


def test_configured_real_vims_can_resolve_vim_info_and_client(
    provider_test_config: ProviderTestConfig,
    real_vim_provider_factory,
):
    assert provider_test_config.vims, "provider config must define at least one VIM"

    for vim_case in provider_test_config.vims:
        provider = real_vim_provider_factory(vim_case)

        vim_info = provider.get_vim_info(vim_case.area)
        vim_client = provider.get_vim_client(vim_case.area)

        assert vim_info == vim_case.vim
        assert vim_client.vim == vim_case.vim


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
        network = _build_net_resource(vim_case, vim_case.create_network)

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


@pytest.mark.provider_destructive
def test_configured_real_vims_can_run_vm_lifecycle(
    provider_test_config: ProviderTestConfig,
    real_vim_provider_factory,
):
    configured_cases = [vim_case for vim_case in provider_test_config.vims if vim_case.vm_lifecycle is not None]
    if not configured_cases:
        pytest.skip("no vm_lifecycle entries configured")

    for vim_case in configured_cases:
        provider = real_vim_provider_factory(vim_case)
        vm_config = vim_case.vm_lifecycle
        vm_resource = _build_vm_resource(vim_case, vm_config)
        attach_network = _build_net_resource(vim_case, vm_config.attach_network)
        vm_destroyed = False

        try:
            provider.create_net(attach_network)
            ok, missing_networks = provider.check_networks_exist_on_vim(
                vim_case.area,
                {attach_network.name},
                resource_group=vim_case.resource_group,
            )
            assert ok is True
            assert attach_network.name not in missing_networks

            provider.create_vm(vm_resource)
            assert vm_resource.created is True
            assert vm_resource.access_ip
            assert vm_resource.management_network in vm_resource.network_interfaces

            _assert_vm_running(provider.check_vm_status(vm_resource), vm_resource)

            facts = provider.configure_vm(
                ProviderLifecycleConfigurator(
                    resource_group=vim_case.resource_group,
                    vm_resource=vm_resource,
                )
            )
            assert facts[CONFIGURE_FACT_NAME] == CONFIGURE_FACT_VALUE

            attached_ips = provider.attach_nets(vm_resource, [attach_network.name])
            assert attached_ips
            assert all(attached_ips)
            assert attach_network.name in vm_resource.additional_networks
            assert attach_network.name in vm_resource.network_interfaces

            provider.reboot_vm(vm_resource, hard=vm_config.hard_reboot)
            _assert_vm_running(_wait_for_vm_running(provider, vm_resource), vm_resource)

            provider.destroy_vm(vm_resource)
            vm_destroyed = True
        finally:
            if vm_resource.created and not vm_destroyed:
                with suppress(Exception):
                    provider.destroy_vm(vm_resource)
            provider.cleanup_resource_group(vim_case.resource_group)
