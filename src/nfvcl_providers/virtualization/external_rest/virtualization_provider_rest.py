from __future__ import annotations

import time
from typing import List, Set, Tuple, Dict, Any, Optional, cast

import httpx
from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_core_models.providers.providers import ProviderData
from nfvcl_core_models.resources import (
    VmResource,
    VmResourceConfiguration,
    NetResource,
    VmStatus, VmResourceAnsibleConfiguration,
)
from nfvcl_core_models.response_model import OssCompliantResponse
from nfvcl_core_models.task import NFVCLTaskStatus, NFVCLTaskStatusType
from nfvcl_core_models.vim.vim_models import VimModel, VimTypeEnum
from nfvcl_providers.vim_clients.rest_vim_client import RESTVimClient
from nfvcl_providers.virtualization.virtualization_provider_interface import (
    VirtualizationProviderInterface,
    VirtualizationProviderData,
    VirtualizationProviderException,
)
from nfvcl_providers_rest.models.virtualization import VmResourceAnsibleConfigurationSerialized, AttachNetPayload, NetworkCheckPayload, NetworkCheckResponse


class ResourceGroupVirtualizationProviderDataRest(ProviderData):
    pass


class RestVimProviderData(ProviderData):
    resource_groups: Dict[str, ResourceGroupVirtualizationProviderDataRest] = Field(default_factory=dict)

    def get_resource_group_data(self, resource_group: str) -> ResourceGroupVirtualizationProviderDataRest:
        if resource_group not in self.resource_groups:
            self.resource_groups[resource_group] = ResourceGroupVirtualizationProviderDataRest()
        return self.resource_groups[resource_group]


class VirtualizationProviderDataRest(VirtualizationProviderData):
    """Data model for REST API provider persistence"""
    vims: Dict[str, RestVimProviderData] = Field(default_factory=dict)

    def get_vim_data(self, vim_name: str) -> RestVimProviderData:
        if vim_name not in self.vims:
            self.vims[vim_name] = RestVimProviderData()
        return self.vims[vim_name]


class VirtualizationProviderRestException(VirtualizationProviderException):
    """Exception for REST API provider errors"""
    pass


class RestProviderContext:
    def __init__(self, vim: VimModel, vim_client: RESTVimClient, resource_group: str):
        self.vim = vim
        self.vim_client = vim_client
        self.resource_group = resource_group
        self.api_base_url = vim.vim_url.rstrip("/")
        self.vim_api_base = f"{self.api_base_url}/vims/{vim.rest_parameters().remote_vim_name}"
        self.rg_api_base = f"{self.vim_api_base}/{resource_group}"
        self.virtualization_api_base = f"{self.rg_api_base}/virtualization"
        self.task_api_base = f"{self.api_base_url}/tasks"
        self.agent_uuid = vim.rest_parameters().local_agent_uuid


class VirtualizationProviderRest(VirtualizationProviderInterface):
    """
    Virtualization provider that uses REST APIs to manage VMs and networks.

    This provider communicates with a remote virtualization backend server
    that implements the required REST API endpoints.
    """
    provider_vim_type = VimTypeEnum.EXTERNAL_REST

    def init(self):
        """Initialize the REST API provider"""
        self.data: VirtualizationProviderDataRest = VirtualizationProviderDataRest()
        self.httpx_client = httpx.Client(follow_redirects=True)

        self.task_poll_interval = 2
        self.task_poll_timeout = 300

    def _get_context(self, area: int, resource_group: str) -> RestProviderContext:
        vim_client = cast(RESTVimClient, self.get_vim_client(area))
        vim = vim_client.vim
        vim_data = self.data.get_vim_data(vim.name)
        if resource_group not in vim_data.resource_groups:
            vim_data.get_resource_group_data(resource_group)
            self.save_to_db()
        return RestProviderContext(
            vim=vim,
            vim_client=vim_client,
            resource_group=resource_group,
        )

    def _delete_resource_group_data(self, vim: VimModel, resource_group: str) -> None:
        vim_data = self.data.vims.get(vim.name)
        if vim_data is not None:
            vim_data.resource_groups.pop(resource_group, None)

    def _resolve_resource_group(self, resource_group: Optional[str]) -> str:
        if not resource_group:
            raise VirtualizationProviderRestException("Resource group is required for REST virtualization operations")
        return resource_group

    def __http_request(self, ctx: RestProviderContext, url: str, method: HttpRequestType, body: Optional[NFVCLBaseModel] = None, query_params: Optional[Dict] = None) -> Any:
        self.logger.spam(f"Sending {method.value} request to {url} with body: {body.model_dump_json() if body else None}")
        response = self.httpx_client.request(method.value, url, json=body.model_dump() if body else None, headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-NFVCL-Agent-ID": ctx.agent_uuid
        }, params=query_params)
        self.logger.spam(f"Response received: {response.json()}, status code: {response.status_code}")
        response.raise_for_status()
        nfvcl_compliant_response = OssCompliantResponse.model_validate(response.json())
        elapsed_time = 0
        while True:
            self.logger.spam(f"Waiting for task completion, elapsed time: {elapsed_time}/{self.task_poll_timeout} seconds")
            resp = self.__http_request_get(ctx, f"{ctx.task_api_base}/{nfvcl_compliant_response.task_id}")
            task_status = NFVCLTaskStatus.model_validate(resp)

            if task_status.error:
                raise VirtualizationProviderRestException(task_status.exception)

            if task_status.status == NFVCLTaskStatusType.DONE:
                self.logger.spam(f"Task completed, result: {task_status.result}")
                return task_status.result
            time.sleep(self.task_poll_interval)
            elapsed_time += self.task_poll_interval
            if elapsed_time > self.task_poll_timeout:
                raise VirtualizationProviderRestException("Timeout waiting for task completion")

    def __http_request_get(self, ctx: RestProviderContext, endpoint: str) -> Any:
        response = self.httpx_client.request("GET", endpoint, headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-NFVCL-Agent-ID": ctx.agent_uuid
        })
        response.raise_for_status()
        return response.json()

    def create_vm(self, vm_resource: VmResource):
        ctx = self._get_context(vm_resource.area, vm_resource.resource_group)
        self.logger.info(f"Creating VM {vm_resource.name}")
        updt = self.__http_request(ctx, f"{ctx.virtualization_api_base}/vms", HttpRequestType.POST, vm_resource)
        vm_resource.update(updt)
        self.logger.success(f"Creating VM {vm_resource.name} finished")

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        ctx = self._get_context(vm_resource_configuration.vm_resource.area, vm_resource_configuration.resource_group)
        self.logger.info(f"Configuring VM {vm_resource_configuration.vm_resource.name}")
        if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):
            serialized_playbook = VmResourceAnsibleConfigurationSerialized(ansible_playbook=vm_resource_configuration.dump_playbook())
            ret = self.__http_request(ctx, f"{ctx.virtualization_api_base}/vms/{vm_resource_configuration.vm_resource.id}/configure", HttpRequestType.PUT, serialized_playbook)
            self.logger.success(f"Configuring VM {vm_resource_configuration.vm_resource.name} finished")
            return ret
        else:
            raise VirtualizationProviderRestException("Unsupported configuration type")

    def check_networks_exist_on_vim(self, area: int, networks_to_check: set[str], resource_group: Optional[str] = None) -> Tuple[bool, Set[str]]:
        ctx = self._get_context(area, self._resolve_resource_group(resource_group))
        response: NetworkCheckResponse = NetworkCheckResponse.model_validate(self.__http_request(ctx, f"{ctx.rg_api_base}/check_networks", HttpRequestType.POST, NetworkCheckPayload(net_names=list(networks_to_check))))
        return response.ok, set(response.missing_nets)

    def attach_nets(self, vm_resource: VmResource, nets_name: List[str]) -> List[str]:
        ctx = self._get_context(vm_resource.area, vm_resource.resource_group)
        ret = self.__http_request(ctx, f"{ctx.virtualization_api_base}/vms/{vm_resource.id}/net", HttpRequestType.POST, AttachNetPayload(net_names=nets_name))
        self.logger.success(f"Networks {nets_name} attached to VM {vm_resource.name}")
        return ret

    def create_net(self, net_resource: NetResource):
        ctx = self._get_context(net_resource.area, net_resource.resource_group)
        self.logger.info(f"Creating NET {net_resource.name}")
        self.__http_request(ctx, f"{ctx.virtualization_api_base}/nets", HttpRequestType.POST, net_resource)
        self.logger.success(f"Creating NET {net_resource.name} finished")

    def destroy_vm(self, vm_resource: VmResource):
        ctx = self._get_context(vm_resource.area, vm_resource.resource_group)
        self.logger.info(f"Destroying VM {vm_resource.name}")
        self.__http_request(ctx, f"{ctx.virtualization_api_base}/vms/{vm_resource.id}", HttpRequestType.DELETE, vm_resource)
        self.logger.success(f"Destroying VM {vm_resource.name} finished")

    def reboot_vm(self, vm_resource: VmResource, hard: bool = False):
        ctx = self._get_context(vm_resource.area, vm_resource.resource_group)
        self.logger.info(f"Restarting VM {vm_resource.name}")
        self.__http_request(ctx, f"{ctx.virtualization_api_base}/vms/{vm_resource.id}/reboot", HttpRequestType.PUT, query_params={"hard": hard})
        self.logger.success(f"Restarting VM {vm_resource.name} finished")

    def check_vm_status(self, vm_resource: VmResource) -> VmStatus:
        ctx = self._get_context(vm_resource.area, vm_resource.resource_group)
        self.logger.info(f"Checking status of VM {vm_resource.name}")
        vm_status = self.__http_request_get(ctx, f"{ctx.virtualization_api_base}/vms/{vm_resource.id}/status")
        self.logger.info(f"VM {vm_resource.name} status: {vm_status}")
        return VmStatus.model_validate(vm_status)

    def cleanup_resource_group(self, resource_group: str):
        resource_group = self._resolve_resource_group(resource_group)
        for vim_name, vim_data in list(self.data.vims.items()):
            if resource_group not in vim_data.resource_groups:
                continue

            vim_client = cast(
                RESTVimClient,
                self.vim_client_pool.get_client_by_vim_name(vim_name, self.provider_vim_type),
            )
            ctx = RestProviderContext(
                vim=vim_client.vim,
                vim_client=vim_client,
                resource_group=resource_group,
            )
            self._final_cleanup_context(ctx)
            self._delete_resource_group_data(ctx.vim, resource_group)
        self.save_to_db()

    def _final_cleanup_context(self, ctx: RestProviderContext) -> None:
        self.logger.info(f"Requesting final cleanup of {ctx.resource_group} on VIM {ctx.vim.name}")
        self.__http_request(ctx, f"{ctx.rg_api_base}", HttpRequestType.DELETE)
        self.logger.success(f"Final cleanup of {ctx.resource_group} on VIM {ctx.vim.name} finished")
