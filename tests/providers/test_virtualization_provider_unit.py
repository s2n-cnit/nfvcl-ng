from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_core_models.resources import VmPowerStatus
from nfvcl_core_models.vim.vim_models import VimTypeEnum
from nfvcl_providers.virtualization.openstack import virtualization_provider_openstack as openstack_module
from nfvcl_providers.virtualization.openstack.virtualization_provider_openstack import (
    VirtualizationProviderOpenstack,
)
from nfvcl_providers.virtualization.proxmox import virtualization_provider_proxmox as proxmox_module
from nfvcl_providers.virtualization.proxmox.virtualization_provider_proxmox import (
    VirtualizationProviderProxmox,
)
from tests.providers.fakes import FakeVimClientPool, SaveSpy, build_vim, build_vm_resource, namespace


def _power_status_value(status) -> str:
    return status.value if hasattr(status, "value") else status


class FakeOpenStackSdk:
    def __init__(self, server_status: str = "ACTIVE"):
        self.server = namespace(id="server-id", status=server_status)
        self.reboot_requests: list[str] = []
        self.compute = namespace(reboot_server=self.reboot_server)

    def get_server(self, server_id: str):
        assert server_id == "server-id"
        return self.server

    def reboot_server(self, server, reboot_type: str) -> None:
        assert server == self.server
        self.reboot_requests.append(reboot_type)


def test_openstack_provider_maps_vm_status_and_checks_ssh(monkeypatch):
    monkeypatch.setattr(openstack_module, "check_ssh_ready", lambda **kwargs: True)
    vm = build_vm_resource()
    vim = build_vim("os-vim", VimTypeEnum.OPENSTACK, area=vm.area)
    sdk = FakeOpenStackSdk(server_status="ACTIVE")
    client = namespace(vim=vim, client=sdk, request_timeout=1)
    provider = VirtualizationProviderOpenstack(vim_client_pool=FakeVimClientPool(client))
    provider.data.get_vim_data(vim.name).get_resource_group_data(vm.resource_group).os_dict[vm.id] = "server-id"

    status = provider.check_vm_status(vm)

    assert status.vm_name == vm.name
    assert _power_status_value(status.power_status) == VmPowerStatus.RUNNING.value
    assert status.ssh_reachable is True


def test_openstack_provider_reboots_soft_and_hard():
    vm = build_vm_resource()
    vim = build_vim("os-vim", VimTypeEnum.OPENSTACK, area=vm.area)
    sdk = FakeOpenStackSdk()
    client = namespace(vim=vim, client=sdk, request_timeout=1)
    provider = VirtualizationProviderOpenstack(vim_client_pool=FakeVimClientPool(client))
    provider.data.get_vim_data(vim.name).get_resource_group_data(vm.resource_group).os_dict[vm.id] = "server-id"

    provider.reboot_vm(vm)
    provider.reboot_vm(vm, hard=True)

    assert sdk.reboot_requests == ["SOFT", "HARD"]


def test_openstack_provider_cleanup_deletes_tracked_resources():
    vim = build_vim("os-vim", VimTypeEnum.OPENSTACK)
    sdk = namespace(
        deleted=[],
        delete_flavor=lambda flavor: sdk.deleted.append(("flavor", flavor)),
        delete_subnet=lambda subnet: sdk.deleted.append(("subnet", subnet)),
        delete_network=lambda network: sdk.deleted.append(("network", network)),
        delete_server=lambda server, wait=True, timeout=1: sdk.deleted.append(("server", server, wait, timeout)),
    )
    client = namespace(vim=vim, client=sdk, request_timeout=1)
    save = SaveSpy()
    pool = FakeVimClientPool(client)
    provider = VirtualizationProviderOpenstack(
        vim_client_pool=pool,
        persistence_function=save,
    )
    rg_data = provider.data.get_vim_data(vim.name).get_resource_group_data("rg")
    rg_data.flavors.append("flavor-a")
    rg_data.subnets.append("subnet-a")
    rg_data.networks.append("net-a")
    rg_data.os_dict["vm-resource"] = "server-a"
    pool.clients.clear()

    provider.cleanup_resource_group("rg")

    assert ("flavor", "flavor-a") in sdk.deleted
    assert ("subnet", "subnet-a") in sdk.deleted
    assert ("network", "net-a") in sdk.deleted
    assert ("server", "server-a", True, 1) in sdk.deleted
    assert provider.data.get_vim_data(vim.name).resource_groups == {}
    assert save.calls == 1


class FakeProxmoxClient:
    def __init__(self, vim):
        self.vim = vim
        self.runtime_ready_calls = 0
        self.requests: list[tuple[str, HttpRequestType]] = []
        self.deleted_vms: list[tuple[str, str]] = []
        self.rebooted_vms: list[tuple[str, bool]] = []

    def ensure_nfvcl_runtime_ready(self, script_content: str) -> None:
        self.runtime_ready_calls += 1

    def get_node_name(self) -> str:
        return "pve"

    def get_vm_status(self, vmid: str):
        self.requests.append((f"get_vm_status:{vmid}", HttpRequestType.GET))
        return {"status": "running"}

    def reboot_vm(self, vmid: str, hard: bool = False) -> None:
        self.rebooted_vms.append((vmid, hard))

    def delete_vm(self, vmid: str, resource_group: str) -> None:
        self.deleted_vms.append((vmid, resource_group))


def test_proxmox_provider_maps_vm_status_and_checks_ssh(monkeypatch):
    monkeypatch.setattr(proxmox_module, "check_ssh_ready", lambda **kwargs: False)
    vm = build_vm_resource()
    vim = build_vim("pve-vim", VimTypeEnum.PROXMOX, area=vm.area)
    client = FakeProxmoxClient(vim)
    provider = VirtualizationProviderProxmox(vim_client_pool=FakeVimClientPool(client))
    provider.data.get_vim_data(vim.name).get_resource_group_data(vm.resource_group).proxmox_dict[vm.id] = "100"

    status = provider.check_vm_status(vm)

    assert status.vm_name == vm.name
    assert _power_status_value(status.power_status) == VmPowerStatus.RUNNING.value
    assert status.ssh_reachable is False
    assert client.runtime_ready_calls == 1
    assert ("get_vm_status:100", HttpRequestType.GET) in client.requests


def test_proxmox_provider_reboots_soft_and_hard():
    vm = build_vm_resource()
    vim = build_vim("pve-vim", VimTypeEnum.PROXMOX, area=vm.area)
    client = FakeProxmoxClient(vim)
    provider = VirtualizationProviderProxmox(vim_client_pool=FakeVimClientPool(client))
    provider.data.get_vim_data(vim.name).get_resource_group_data(vm.resource_group).proxmox_dict[vm.id] = "100"

    provider.reboot_vm(vm)
    provider.reboot_vm(vm, hard=True)

    assert client.rebooted_vms == [("100", False), ("100", True)]


def test_proxmox_provider_destroy_vm_uses_client_delete_vm():
    vm = build_vm_resource()
    vim = build_vim("pve-vim", VimTypeEnum.PROXMOX, area=vm.area)
    client = FakeProxmoxClient(vim)
    provider = VirtualizationProviderProxmox(vim_client_pool=FakeVimClientPool(client))
    rg_data = provider.data.get_vim_data(vim.name).get_resource_group_data(vm.resource_group)
    rg_data.proxmox_dict[vm.id] = "100"

    provider.destroy_vm(vm)

    assert client.deleted_vms == [("100", vm.resource_group)]
    assert rg_data.proxmox_dict == {}


def test_proxmox_provider_cleanup_deletes_leftover_vms():
    vim = build_vim("pve-vim", VimTypeEnum.PROXMOX)
    client = FakeProxmoxClient(vim)
    save = SaveSpy()
    provider = VirtualizationProviderProxmox(
        vim_client_pool=FakeVimClientPool(client),
        persistence_function=save,
    )
    rg_data = provider.data.get_vim_data(vim.name).get_resource_group_data("rg")
    rg_data.proxmox_dict["vm-resource"] = "100"

    provider.cleanup_resource_group("rg")

    assert client.deleted_vms == [("100", "rg")]
    assert provider.data.get_vim_data(vim.name).resource_groups == {}
    assert save.calls == 1
