from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_core_models.resources import NetResource, VmPowerStatus
from nfvcl_core_models.vim.vim_models import VimTypeEnum
from nfvcl_providers.vim_clients.proxmox_vim_client import ProxmoxVimClient, proxmox_sdn_vnet_identifier
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


def test_openstack_provider_attach_nets_refreshes_server_before_mapping_nics(monkeypatch):
    monkeypatch.setattr(
        openstack_module,
        "configure_vm_ansible",
        lambda *args, **kwargs: {"interfaces_mac": "eth0: 00:00:00:00:00:01\neth1: 00:00:00:00:00:02"},
    )

    vm = build_vm_resource()
    vim = build_vim("os-vim", VimTypeEnum.OPENSTACK, area=vm.area)
    stale_server = namespace(
        id="server-id",
        addresses={
            "mgmt": [
                {
                    "OS-EXT-IPS:type": "fixed",
                    "addr": "192.0.2.20",
                    "OS-EXT-IPS-MAC:mac_addr": "00:00:00:00:00:01",
                }
            ],
        },
    )
    refreshed_server = namespace(
        id="server-id",
        addresses={
            "mgmt": [
                {
                    "OS-EXT-IPS:type": "fixed",
                    "addr": "192.0.2.20",
                    "OS-EXT-IPS-MAC:mac_addr": "00:00:00:00:00:01",
                }
            ],
            "data": [
                {
                    "OS-EXT-IPS:type": "fixed",
                    "addr": "10.0.0.20",
                    "OS-EXT-IPS-MAC:mac_addr": "00:00:00:00:00:02",
                }
            ],
        },
    )
    sdk = namespace(attached=False, get_server_calls=0)

    def get_server(server_id: str):
        assert server_id == "server-id"
        sdk.get_server_calls += 1
        return refreshed_server if sdk.attached else stale_server

    def create_server_interface(server_id: str, net_id: str):
        assert server_id == "server-id"
        assert net_id == "data-id"
        sdk.attached = True
        return namespace(mac_addr="00:00:00:00:00:02")

    sdk.get_server = get_server
    sdk.compute = namespace(create_server_interface=create_server_interface)

    def get_network(network_name: str):
        return namespace(id=f"{network_name}-id", subnet_ids=[f"{network_name}-subnet"])

    def get_network_details(network_names: list[str]):
        cidrs = {"mgmt": "192.0.2.0/24", "data": "10.0.0.0/24"}
        return {network_name: namespace(cidr=cidrs[network_name]) for network_name in network_names}

    disabled_port_security_for: list[str] = []
    client = namespace(
        vim=vim,
        client=sdk,
        request_timeout=1,
        get_network=get_network,
        get_network_details=get_network_details,
        disable_port_security_all_ports=lambda vm_resource, server_obj: disabled_port_security_for.append(server_obj.id),
    )
    provider = VirtualizationProviderOpenstack(vim_client_pool=FakeVimClientPool(client))
    provider.data.get_vim_data(vim.name).get_resource_group_data(vm.resource_group).os_dict[vm.id] = "server-id"

    ips = provider.attach_nets(vm, ["data"])

    assert ips == ["10.0.0.20"]
    assert vm.additional_networks == ["data"]
    assert vm.network_interfaces["data"][0].fixed.interface_name == "eth1"
    assert disabled_port_security_for == ["server-id"]
    assert sdk.get_server_calls == 2


class FakeProxmoxClient:
    def __init__(self, vim):
        self.vim = vim
        self.runtime_ready_calls = 0
        self.requests: list[tuple[str, HttpRequestType]] = []
        self.deleted_vms: list[tuple[str, str]] = []
        self.rebooted_vms: list[tuple[str, bool]] = []
        self.created_vnets: list[tuple[str, str]] = []
        self.created_subnets: list[tuple[str, str, str, str, str]] = []

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

    def create_sdn_vnet(self, identifier: str, name: str) -> None:
        self.created_vnets.append((identifier, name))

    def create_sdn_subnet(self, vnet_id: str, cidr: str, start_dhcp: str, end_dhcp: str, gateway: str) -> None:
        self.created_subnets.append((vnet_id, cidr, start_dhcp, end_dhcp, gateway))


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


def test_proxmox_provider_create_net_uses_sha1_vnet_identifier():
    vim = build_vim("pve-vim", VimTypeEnum.PROXMOX)
    client = FakeProxmoxClient(vim)
    save = SaveSpy()
    provider = VirtualizationProviderProxmox(
        vim_client_pool=FakeVimClientPool(client),
        persistence_function=save,
    )
    net = NetResource(
        resource_group="rg",
        area=1,
        name="nfvcl-provider-test-attach-net-with-a-long-name",
        cidr="10.251.0.0/24",
    )
    expected_identifier = proxmox_sdn_vnet_identifier(net.name)

    provider.create_net(net)

    assert len(expected_identifier) == 8
    assert expected_identifier[0] == "N"
    assert client.created_vnets == [(expected_identifier, net.name)]
    assert client.created_subnets == [(expected_identifier, net.cidr, "10.251.0.2", "10.251.0.253", "10.251.0.254")]
    assert provider.data.get_vim_data(vim.name).get_resource_group_data(net.resource_group).proxmox_vnet[net.name] == expected_identifier
    assert save.calls == 2


def test_proxmox_vim_client_check_networks_matches_full_vnet_names_to_hashed_ids():
    full_vnet_name = "nfvcl-provider-test-attach-net-with-a-long-name"
    hashed_vnet_id = proxmox_sdn_vnet_identifier(full_vnet_name)
    client = ProxmoxVimClient.__new__(ProxmoxVimClient)
    client.vim = build_vim("pve-vim", VimTypeEnum.PROXMOX)
    client.closed = False
    client.get_node_name = lambda: "pve"

    def execute_proxmox_request(url: str, r_type: HttpRequestType, **kwargs):
        if url == "nodes/pve/network":
            return [
                {
                    "iface": "vmbr0",
                    "address": "192.0.2.10",
                }
            ]
        if url == "/cluster/sdn/vnets":
            return [
                {
                    "vnet": hashed_vnet_id,
                    "alias": "different-alias",
                    "zone": client.vim.proxmox_parameters().proxmox_sdn_zone,
                }
            ]
        raise AssertionError(f"Unexpected Proxmox request: {r_type} {url}")

    client.execute_proxmox_request = execute_proxmox_request

    ok, missing_networks = client.check_networks({"vmbr0", full_vnet_name})
    assert ok is True
    assert missing_networks == set()

    ok, missing_networks = client.check_networks({"vmbr0", full_vnet_name, "missing-net"})
    assert ok is False
    assert missing_networks == {"missing-net"}


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


def test_openstack_provider_get_networks_and_get_net():
    import pytest
    from nfvcl_core_models.network.network_models import NetworkModel, NetworkTypeEnum
    from nfvcl_providers.virtualization.openstack.virtualization_provider_openstack import VirtualizationProviderOpenstackException

    vim = build_vim("os-vim", VimTypeEnum.OPENSTACK)

    net1 = namespace(name="net-1", subnet_ids=["sub-1"], is_external=False, provider_network_type="vlan")
    net2 = namespace(name="net-2", subnet_ids=["sub-2"], is_external=True, provider_network_type="vxlan")
    subnet1 = namespace(
        cidr="192.168.1.0/24",
        gateway_ip="192.168.1.1",
        allocation_pools=[{"start": "192.168.1.10", "end": "192.168.1.100"}],
        dns_nameservers=["8.8.8.8"],
        enable_dhcp=True,
    )
    subnet2 = namespace(
        cidr="10.0.0.0/16",
        gateway_ip="10.0.0.1",
        allocation_pools=[],
        dns_nameservers=[],
        enable_dhcp=False,
    )

    subnets_map = {"sub-1": subnet1, "sub-2": subnet2}
    sdk = namespace(get_subnet=lambda sub_id: subnets_map.get(sub_id))

    class FakeOpenStackVimClient:
        def __init__(self):
            self.vim = vim
            self.client = sdk

        def get_available_networks(self):
            return {"net-1": net1, "net-2": net2}

        def get_network(self, net_name: str):
            return {"net-1": net1, "net-2": net2}.get(net_name)

    client = FakeOpenStackVimClient()
    provider = VirtualizationProviderOpenstack(vim_client_pool=FakeVimClientPool(client))

    networks = provider.get_networks()
    assert len(networks) == 2
    assert isinstance(networks[0], NetworkModel)
    assert networks[0].name == "net-1"
    assert str(networks[0].cidr) == "192.168.1.0/24"
    assert str(networks[0].gateway_ip) == "192.168.1.1"
    assert len(networks[0].allocation_pool) == 1
    assert networks[0].dhcp is True
    assert networks[0].external is False
    assert networks[0].type == NetworkTypeEnum.vlan

    assert networks[1].name == "net-2"
    assert networks[1].type == NetworkTypeEnum.vxlan
    assert networks[1].external is True

    single_net = provider.get_net("net-1")
    assert isinstance(single_net, NetworkModel)
    assert single_net.name == "net-1"

    with pytest.raises(VirtualizationProviderOpenstackException):
        provider.get_net("nonexistent-net")


def test_proxmox_and_rest_provider_get_networks_get_net_pass():
    from nfvcl_providers.virtualization.external_rest.virtualization_provider_rest import VirtualizationProviderRest

    pve_vim = build_vim("pve-vim", VimTypeEnum.PROXMOX)
    pve_client = FakeProxmoxClient(pve_vim)
    pve_provider = VirtualizationProviderProxmox(vim_client_pool=FakeVimClientPool(pve_client))

    assert pve_provider.get_networks() is None
    assert pve_provider.get_net("net-1") is None

    rest_vim = build_vim("rest-vim", VimTypeEnum.EXTERNAL_REST)
    rest_client = namespace(vim=rest_vim)
    rest_provider = VirtualizationProviderRest(vim_client_pool=FakeVimClientPool(rest_client))

    assert rest_provider.get_networks() is None
    assert rest_provider.get_net("net-1") is None
