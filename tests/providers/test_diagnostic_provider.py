import pytest

from nfvcl_core_models.providers.diagnostic import DiagnosticProviderException
from nfvcl_providers.diagnostic import diagnostic_provider as diagnostic_module
from nfvcl_providers.diagnostic.diagnostic_provider import DiagnosticProvider, RpcapdVmOperation
from tests.providers.fakes import SaveSpy, build_vm_resource


def test_diagnostic_provider_installs_tracks_and_reports_rpcapd(monkeypatch: pytest.MonkeyPatch):
    operations: list[RpcapdVmOperation] = []

    def fake_configure_vm_ansible(configurator, resource_group: str, logger_override=None):
        operations.append(configurator.operation)
        if configurator.operation == RpcapdVmOperation.STATUS:
            return {
                "rpcapd_installed": "true",
                "rpcapd_service_state": "active",
            }
        return {}

    monkeypatch.setattr(diagnostic_module, "configure_vm_ansible", fake_configure_vm_ansible)

    vm = build_vm_resource()
    save = SaveSpy()
    provider = DiagnosticProvider(persistence_function=save)

    status = provider.install_rpcapd(vm, download_url="https://example.invalid/rpcapd")

    assert status.vm_name == vm.name
    assert status.installed is True
    assert status.running is True
    assert provider.data.rpcapd_vm_deployments[0].vm_resource == vm
    assert operations == [RpcapdVmOperation.INSTALL, RpcapdVmOperation.STATUS]
    assert save.calls == 1


def test_diagnostic_provider_requires_managed_vm_for_service_operations(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(diagnostic_module, "configure_vm_ansible", lambda *args, **kwargs: {})
    provider = DiagnosticProvider()

    with pytest.raises(DiagnosticProviderException):
        provider.start_rpcapd(build_vm_resource())


def test_diagnostic_provider_cleanup_uninstalls_managed_deployments(monkeypatch: pytest.MonkeyPatch):
    operations: list[RpcapdVmOperation] = []

    def fake_configure_vm_ansible(configurator, resource_group: str, logger_override=None):
        operations.append(configurator.operation)
        if configurator.operation == RpcapdVmOperation.STATUS:
            return {
                "rpcapd_installed": "true",
                "rpcapd_service_state": "active",
            }
        return {}

    monkeypatch.setattr(diagnostic_module, "configure_vm_ansible", fake_configure_vm_ansible)

    vm = build_vm_resource(resource_group="cleanup-rg")
    save = SaveSpy()
    provider = DiagnosticProvider(persistence_function=save)
    provider.install_rpcapd(vm)

    provider.cleanup_resource_group("cleanup-rg")

    assert provider.data.rpcapd_vm_deployments == []
    assert RpcapdVmOperation.UNINSTALL in operations
    assert save.calls == 3
