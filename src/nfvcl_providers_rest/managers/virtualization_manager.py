import threading
from typing import Dict, List, Optional

from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core.managers.task_manager import TaskManager
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.resources import VmResource, VmStatus, NetResource
from nfvcl_core_models.vim.vim_models import VimModel
from nfvcl_providers.vim_clients.vim_client import VimClient
from nfvcl_providers.virtualization import vim_type_to_vim_client_mapping, vim_type_to_provider_mapping
from nfvcl_providers.virtualization.common.utils import wait_for_ssh_to_be_ready, configure_machine_ansible
from nfvcl_providers.virtualization.virtualization_provider_interface import VirtualizationProviderInterface
from nfvcl_providers_rest.database.agent_repository import NFVCLProviderAgentRepository
from nfvcl_providers_rest.database.vim_repository import NFVCLProviderVimRepository
from nfvcl_providers_rest.models.db import NFVCLProviderAgent, NFVCLProviderResourceGroup
from nfvcl_providers_rest.models.virtualization import VmResourceAnsibleConfigurationSerialized, AttachNetPayload, NetworkCheckPayload, NetworkCheckResponse


class VirtualizationManager(GenericManager):
    def __init__(self, task_manager: TaskManager, vim_repository: NFVCLProviderVimRepository, agent_repository: NFVCLProviderAgentRepository):
        super().__init__()
        self.task_manager = task_manager
        self.vim_repository = vim_repository
        self._agent_repository = agent_repository
        self.loaded_providers: Dict[str, Dict[str, VirtualizationProviderInterface]] = {}
        self.vim_clients: Dict[str, VimClient] = {}
        self.cached_vims: Dict[str, VimModel] = {}

        # We keep a copy of the data here to avoid multiple db calls and race conditions
        self.agent_data_lock: threading.Lock = threading.Lock()
        self.agents_data: Dict[str, NFVCLProviderAgent] = {}
        # Load the agent data from the db
        for agent in self._agent_repository.get_all():
            self.agents_data[agent.uuid] = agent

    def update_agent_data_db(self):
        self.logger.debug("Updating agent data in db")
        with self.agent_data_lock:
            self._agent_repository.update_all(list(self.agents_data.values()))

    def _get_or_create_resource_group(self, rg_id: str, agent_uuid: str) -> Optional[NFVCLProviderResourceGroup]:
        with self.agent_data_lock:
            agent_data = self.agents_data.get(agent_uuid, None)
            if not agent_data:
                self.agents_data[agent_uuid] = NFVCLProviderAgent(uuid=agent_uuid)
            agent_data = self.agents_data[agent_uuid]
            if not agent_data.resource_groups.get(rg_id):
                agent_data.resource_groups[rg_id] = NFVCLProviderResourceGroup(id=rg_id)
            return agent_data.resource_groups[rg_id]

    def _get_vim_client(self, vim: VimModel) -> VimClient:
        if vim.name not in self.vim_clients:
            self.vim_clients[vim.name] = vim_type_to_vim_client_mapping[vim.vim_type](vim)
        return self.vim_clients[vim.name]

    def get_virtualization_provider(self, vim_name: str, resource_group_id: str, agent_uuid: str) -> VirtualizationProviderInterface:
        if vim_name not in self.cached_vims:
            self.cached_vims[vim_name] = self.vim_repository.get_vim(vim_name)
        vim: VimModel = self.cached_vims[vim_name]

        # Check if vim name exists in loaded_providers
        if vim.name not in self.loaded_providers:
            self.loaded_providers[vim.name] = {}

        # Check if resource_group_id exists for this vim
        if resource_group_id not in self.loaded_providers[vim.name]:
            # Create persistence function to save provider data
            def persistence_function():
                provider = self.loaded_providers[vim.name][resource_group_id]

                current_rg = self._get_or_create_resource_group(resource_group_id, agent_uuid)
                current_rg.provider_data[vim.name] = provider.data
                self.update_agent_data_db()

            vim_client = self._get_vim_client(vim)
            ProviderClass: type[VirtualizationProviderInterface] = vim_type_to_provider_mapping[vim.vim_type]
            provider = ProviderClass(
                area=0,
                blueprint_id=resource_group_id,
                vim_client=vim_client,
                persistence_function=persistence_function
            )
            provider.init()
            saved_rg = self._get_or_create_resource_group(resource_group_id, agent_uuid)
            saved_data = None
            if saved_rg:
                saved_data = saved_rg.provider_data.get(vim.name)
                if saved_data:
                    provider.data = provider.data.model_validate(saved_data.model_dump())
            self.loaded_providers[vim.name][resource_group_id] = provider
            self.logger.info(
                f"Created new provider for resource_group_id={resource_group_id} for vim={vim.name}, from_db={saved_rg is not None and saved_data is not None}"
            )

        return self.loaded_providers[vim.name][resource_group_id]

    def get_vm_resource(self, resource_group_id: str, vm_id: str, agent_uuid: str) -> VmResource:
        rg = self._get_or_create_resource_group(resource_group_id, agent_uuid)
        return rg.vm_resources[vm_id]

    def create_vm(self, vim_name: str, resource_group_id: str, vm_resource: VmResource, agent_uuid: str) -> VmResource:
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)
        rg = self._get_or_create_resource_group(resource_group_id, agent_uuid)
        rg.vm_resources[vm_resource.id] = vm_resource
        self.update_agent_data_db()
        provider.create_vm(vm_resource)
        return vm_resource

    def list_vms(self, vim_name: str, resource_group_id: str, agent_uuid: str) -> List[VmResource]:
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)
        rg = self._get_or_create_resource_group(resource_group_id, agent_uuid)
        return list(rg.vm_resources.values())

    def vm_info(self, vim_name: str, resource_group_id: str, vm_id: str, agent_uuid: str) -> VmResource:
        return self.get_vm_resource(resource_group_id, vm_id, agent_uuid)

    def vm_status(self, vim_name: str, resource_group_id: str, vm_id: str, agent_uuid: str) -> VmStatus:
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)
        return provider.check_vm_status(self.get_vm_resource(resource_group_id, vm_id, agent_uuid))

    def destroy_vm(self, vim_name: str, resource_group_id: str, vm_id: str, agent_uuid: str):
        rg = self._get_or_create_resource_group(resource_group_id, agent_uuid)
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)
        ret = rg.vm_resources.pop(vm_id, None)
        if not ret:
            raise NFVCLCoreException(f"VM {vm_id} not found in resource group {resource_group_id}", http_equivalent_code=404)
        provider.destroy_vm(ret)
        self.update_agent_data_db()
        return ret

    def configure_vm(self, vim_name: str, resource_group_id: str, vm_id: str, vm_resource_configuration: VmResourceAnsibleConfigurationSerialized, agent_uuid: str) -> dict:
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)

        if vm_id not in self._get_or_create_resource_group(resource_group_id, agent_uuid).vm_resources:
            raise NFVCLCoreException(f"VM {vm_id} not found in resource group {resource_group_id}", http_equivalent_code=404)

        vm_resource = self._get_or_create_resource_group(resource_group_id, agent_uuid).vm_resources[vm_id]

        # TODO could be possible to inject an ansible playbook and make it run on the NFVCL machine itself

        wait_for_ssh_to_be_ready(
            vm_resource.access_ip,
            22,
            vm_resource.username,
            vm_resource.password,
            300,
            5,
            logger_override=self.logger
        )

        fact_cache = configure_machine_ansible(
            vm_resource.access_ip,
            vm_resource.username,
            vm_resource.password,
            vm_resource_configuration.ansible_playbook,
            logger_override=self.logger
        )

        return fact_cache

    def reboot_vm(self, vim_name: str, resource_group_id: str, vm_id: str, agent_uuid: str, hard: bool = False):
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)
        provider.reboot_vm(self.get_vm_resource(resource_group_id, vm_id, agent_uuid), hard)

    def attach_net(self, vim_name: str, resource_group_id: str, vm_id: str, body: AttachNetPayload, agent_uuid: str) -> List[str]:
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)
        return provider.attach_nets(self.get_vm_resource(resource_group_id, vm_id, agent_uuid), body.net_names)

    def list_attached_nets(self, vim_name: str, resource_group_id: str, vm_id: str, agent_uuid: str) -> List[NetResource]:
        raise NotImplementedError("Function not implemented yet")

    def detach_net(self, vim_name: str, resource_group_id: str, vm_id: str, net_name: str, agent_uuid: str):
        raise NotImplementedError("Function not implemented yet")

    def create_net(self, vim_name: str, resource_group_id: str, net_resource: NetResource, agent_uuid: str):
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)

        # Create the network using the provider
        provider.create_net(net_resource)

        # Store the network resource in the resource group
        rg = self._get_or_create_resource_group(resource_group_id, agent_uuid)
        rg.net_resources[net_resource.id] = net_resource
        self.update_agent_data_db()

        self.logger.info(f"Network {net_resource.name} created")

    def list_nets(self, vim_name: str, resource_group_id: str, agent_uuid: str) -> List[NetResource]:
        raise NotImplementedError("Function not implemented yet")

    def net_info(self, vim_name: str, resource_group_id: str, net_name: str, agent_uuid: str) -> NetResource:
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)
        rg = self._get_or_create_resource_group(resource_group_id, agent_uuid)

        # Find the network resource
        if net_name not in rg.net_resources:
            raise NFVCLCoreException(f"Network {net_name} not found in resource group {resource_group_id}", http_equivalent_code=404)

        net_resource = rg.net_resources[net_name]
        return net_resource

    def destroy_net(self, vim_name: str, resource_group_id: str, net_name: str, agent_uuid: str):
        raise NotImplementedError("Function not implemented yet")

    def final_cleanup(self, vim_name: str, resource_group_id: str, agent_uuid: str):
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)
        provider.final_cleanup()

        with self.agent_data_lock:
            self.agents_data[agent_uuid].resource_groups.pop(resource_group_id, None)
        self.update_agent_data_db()

    def check_networks(self, vim_name: str, resource_group_id: str, network_check_payload: NetworkCheckPayload ,agent_uuid: str) -> NetworkCheckResponse:
        provider = self.get_virtualization_provider(vim_name, resource_group_id, agent_uuid)
        ok, missing_nets = provider.check_networks(set(network_check_payload.net_names))
        return NetworkCheckResponse(ok=ok, missing_nets=list(missing_nets))
