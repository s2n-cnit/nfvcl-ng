import pytest

from nfvcl_core_models.resources import NetResource, VmResource, VmResourceConfiguration, VmStatus
from nfvcl_core_models.vim.vim_models import VimModel, VimTypeEnum
from nfvcl_providers.virtualization.virtualization_provider_interface import VirtualizationProviderData, VirtualizationProviderInterface
from nfvcl_providers_rest.database.agent_repository import NFVCLProviderAgentRepository
from nfvcl_providers_rest.managers import virtualization_manager as virtualization_manager_module
from nfvcl_providers_rest.managers.virtualization_manager import VirtualizationManager
from nfvcl_providers_rest.models.db import NFVCLProviderAgent
from nfvcl_providers_rest.models.virtualization import AttachNetPayload
from tests.providers.fakes import build_vim, build_vm_resource


class FakeAgentRepository:
    def __init__(self, agents: list[NFVCLProviderAgent] | None = None):
        self.agents = agents or []
        self.snapshots: list[list[NFVCLProviderAgent]] = []

    def get_all(self) -> list[NFVCLProviderAgent]:
        return self.agents

    def update_all(self, agent_data_list: list[NFVCLProviderAgent]) -> None:
        self.snapshots.append([agent.model_copy(deep=True) for agent in agent_data_list])
        self.agents = self.snapshots[-1]

    def latest_agent(self, agent_uuid: str) -> NFVCLProviderAgent:
        return {agent.uuid: agent for agent in self.snapshots[-1]}[agent_uuid]


class FakeVimRepository:
    def __init__(self, vim: VimModel):
        self.vim = vim

    def get_vim(self, vim_name: str) -> VimModel:
        if vim_name != self.vim.name:
            raise ValueError(f"Unexpected VIM {vim_name}")
        return self.vim


class FakeVirtualizationProvider(VirtualizationProviderInterface):
    provider_vim_type = VimTypeEnum.OPENSTACK
    fail_destroy = False
    instances: list["FakeVirtualizationProvider"] = []

    def init(self):
        self.data = VirtualizationProviderData()
        self.destroyed_vms: list[str] = []
        self.cleaned_resource_groups: list[str] = []
        self.instances.append(self)

    def create_vm(self, vm_resource: VmResource):
        vm_resource.created = True
        vm_resource.access_ip = "198.51.100.10"

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        return {}

    def check_networks_exist_on_vim(self, area: int, networks_to_check: set[str], resource_group: str | None = None) -> tuple[bool, set[str]]:
        return True, set()

    def attach_nets(self, vm_resource: VmResource, nets_name: list[str]) -> list[str]:
        vm_resource.additional_networks.extend(nets_name)
        return ["198.51.100.20"]

    def create_net(self, net_resource: NetResource):
        pass

    def destroy_vm(self, vm_resource: VmResource):
        if self.fail_destroy:
            raise RuntimeError("destroy failed")
        self.destroyed_vms.append(vm_resource.id)

    def reboot_vm(self, vm_resource: VmResource, hard: bool = False):
        pass

    def check_vm_status(self, vm_resource: VmResource) -> VmStatus:
        raise NotImplementedError

    def cleanup_resource_group(self, resource_group: str):
        self.cleaned_resource_groups.append(resource_group)


@pytest.fixture(autouse=True)
def fake_virtualization_provider(monkeypatch: pytest.MonkeyPatch):
    FakeVirtualizationProvider.fail_destroy = False
    FakeVirtualizationProvider.instances = []
    monkeypatch.setattr(
        virtualization_manager_module,
        "vim_type_to_provider_mapping",
        {VimTypeEnum.OPENSTACK: FakeVirtualizationProvider},
    )


def build_manager(agent_repository: FakeAgentRepository | None = None) -> VirtualizationManager:
    return VirtualizationManager(
        task_manager=None,
        vim_repository=FakeVimRepository(build_vim("vim_a", VimTypeEnum.OPENSTACK)),
        agent_repository=agent_repository or FakeAgentRepository(),
    )


def test_agent_repository_upserts_new_agents():
    calls = []

    class FakeCollection:
        def update_one(self, query: dict, update: dict, upsert: bool = False):
            calls.append((query, update, upsert))

    repository = NFVCLProviderAgentRepository.__new__(NFVCLProviderAgentRepository)
    repository.collection = FakeCollection()

    repository.update_all([NFVCLProviderAgent(uuid="agent-a")])

    assert calls[0][0] == {"uuid": "agent-a"}
    assert calls[0][2] is True


def test_provider_cache_is_scoped_by_agent_uuid():
    manager = build_manager()

    agent_a_provider = manager.get_virtualization_provider("vim_a", "shared-rg", "agent-a")
    agent_b_provider = manager.get_virtualization_provider("vim_a", "shared-rg", "agent-b")

    assert agent_a_provider is not agent_b_provider
    assert len(FakeVirtualizationProvider.instances) == 2


def test_create_vm_and_attach_net_persist_provider_mutations():
    agent_repository = FakeAgentRepository()
    manager = build_manager(agent_repository)
    vm_resource = build_vm_resource(created=False, resource_group="rg")

    manager.create_vm("vim_a", "rg", vm_resource, "agent-a")

    persisted_vm = agent_repository.latest_agent("agent-a").resource_groups["rg"].vm_resources[vm_resource.id]
    assert persisted_vm.created is True
    assert persisted_vm.access_ip == "198.51.100.10"

    manager.attach_net("vim_a", "rg", vm_resource.id, AttachNetPayload(net_names=["data-net"]), "agent-a")

    persisted_vm = agent_repository.latest_agent("agent-a").resource_groups["rg"].vm_resources[vm_resource.id]
    assert persisted_vm.additional_networks == ["data-net"]


def test_destroy_vm_keeps_resource_when_provider_destroy_fails():
    manager = build_manager()
    vm_resource = build_vm_resource(created=True, resource_group="rg")
    manager.create_vm("vim_a", "rg", vm_resource, "agent-a")
    FakeVirtualizationProvider.instances[0].fail_destroy = True

    with pytest.raises(RuntimeError, match="destroy failed"):
        manager.destroy_vm("vim_a", "rg", vm_resource.id, "agent-a")

    rg = manager._get_or_create_resource_group("rg", "agent-a")
    assert vm_resource.id in rg.vm_resources


def test_final_cleanup_removes_resource_group_and_cached_provider():
    agent_repository = FakeAgentRepository()
    manager = build_manager(agent_repository)

    provider = manager.get_virtualization_provider("vim_a", "rg", "agent-a")
    manager.final_cleanup("vim_a", "rg", "agent-a")

    assert "rg" not in agent_repository.latest_agent("agent-a").resource_groups
    assert FakeVirtualizationProvider.instances[0].cleaned_resource_groups == ["rg"]
    assert (("agent-a", "vim_a", "rg")) not in manager.loaded_providers
    assert manager.get_virtualization_provider("vim_a", "rg", "agent-a") is not provider
