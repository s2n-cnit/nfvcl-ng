import time
from typing import List, Set, Tuple, Dict, Any, Optional

import httpx

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_core_models.resources import (
    VmResource,
    VmResourceConfiguration,
    NetResource,
    VmStatus, VmResourceAnsibleConfiguration,
)
from nfvcl_core_models.response_model import OssCompliantResponse
from nfvcl_core_models.task import NFVCLTaskStatus, NFVCLTaskStatusType
from nfvcl_providers.virtualization.virtualization_provider_interface import (
    VirtualizationProviderInterface,
    VirtualizationProviderData,
    VirtualizationProviderException,
)
from nfvcl_providers_rest.models.virtualization import VmResourceAnsibleConfigurationSerialized, AttachNetPayload, NetworkCheckPayload, NetworkCheckResponse


class VirtualizationProviderDataRest(VirtualizationProviderData):
    """Data model for REST API provider persistence"""
    pass


class VirtualizationProviderRestException(VirtualizationProviderException):
    """Exception for REST API provider errors"""
    pass


class VirtualizationProviderRest(VirtualizationProviderInterface):
    """
    Virtualization provider that uses REST APIs to manage VMs and networks.

    This provider communicates with a remote virtualization backend server
    that implements the required REST API endpoints.
    """

    def init(self):
        """Initialize the REST API provider"""
        self.data: VirtualizationProviderDataRest = VirtualizationProviderDataRest()
        self.api_base_url = self.vim.vim_url
        self.api_base_url = self.api_base_url.rstrip("/")

        self.vim_api_base = f"{self.api_base_url}/vims/{self.vim.rest_parameters().remote_vim_name}"
        self.rg_api_base = f"{self.vim_api_base}/{self.blueprint_id}"
        self.virtualization_api_base = f"{self.rg_api_base}/virtualization"
        self.task_api_base = f"{self.api_base_url}/tasks"

        self.agent_uuid = self.vim.rest_parameters().local_agent_uuid

        self.httpx_client = httpx.Client(follow_redirects=True)

        self.task_poll_interval = 2
        self.task_poll_timeout = 300

        self.logger.info(f"REST API Provider initialized with base URL: {self.api_base_url} and vim name: {self.vim.rest_parameters().remote_vim_name}")

    def __http_request(self, url: str, method: HttpRequestType, body: Optional[NFVCLBaseModel] = None, query_params: Optional[Dict] = None) -> Any:
        self.logger.spam(f"Sending {method.value} request to {url} with body: {body.model_dump_json() if body else None}")
        response = self.httpx_client.request(method.value, url, json=body.model_dump() if body else None, headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-NFVCL-Agent-ID": self.agent_uuid
        }, params=query_params)
        self.logger.spam(f"Response received: {response.json()}, status code: {response.status_code}")
        response.raise_for_status()
        nfvcl_compliant_response = OssCompliantResponse.model_validate(response.json())
        elapsed_time = 0
        while True:
            self.logger.spam(f"Waiting for task completion, elapsed time: {elapsed_time}/{self.task_poll_timeout} seconds")
            resp = self.__http_request_get(f"{self.task_api_base}/{nfvcl_compliant_response.task_id}")
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

    def __http_request_get(self, endpoint: str) -> Any:
        response = self.httpx_client.request("GET", endpoint, headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-NFVCL-Agent-ID": self.agent_uuid
        })
        response.raise_for_status()
        return response.json()

    def create_vm(self, vm_resource: VmResource):
        self.logger.info(f"Creating VM {vm_resource.name}")
        updt = self.__http_request(f"{self.virtualization_api_base}/vms", HttpRequestType.POST, vm_resource)
        vm_resource.update(updt)
        self.logger.success(f"Creating VM {vm_resource.name} finished")

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        self.logger.info(f"Configuring VM {vm_resource_configuration.vm_resource.name}")
        if isinstance(vm_resource_configuration, VmResourceAnsibleConfiguration):
            serialized_playbook = VmResourceAnsibleConfigurationSerialized(ansible_playbook=vm_resource_configuration.dump_playbook())
            ret = self.__http_request(f"{self.virtualization_api_base}/vms/{vm_resource_configuration.vm_resource.id}/configure", HttpRequestType.PUT, serialized_playbook)
            self.logger.success(f"Configuring VM {vm_resource_configuration.vm_resource.name} finished")
            return ret
        else:
            raise VirtualizationProviderRestException("Unsupported configuration type")

    def check_networks(self, networks_to_check: set[str]) -> Tuple[bool, Set[str]]:
        response: NetworkCheckResponse = NetworkCheckResponse.model_validate(self.__http_request(f"{self.rg_api_base}/check_networks", HttpRequestType.POST, NetworkCheckPayload(net_names=list(networks_to_check))))
        return response.ok, set(response.missing_nets)

    def attach_nets(self, vm_resource: VmResource, nets_name: List[str]) -> List[str]:
        ret = self.__http_request(f"{self.virtualization_api_base}/vms/{vm_resource.id}/net", HttpRequestType.POST, AttachNetPayload(net_names=nets_name))
        self.logger.success(f"Networks {nets_name} attached to VM {vm_resource.name}")
        return ret

    def create_net(self, net_resource: NetResource):
        self.logger.info(f"Creating NET {net_resource.name}")
        self.__http_request(f"{self.virtualization_api_base}/nets", HttpRequestType.POST, net_resource)
        self.logger.success(f"Creating NET {net_resource.name} finished")

    def destroy_vm(self, vm_resource: VmResource):
        self.logger.info(f"Destroying VM {vm_resource.name}")
        self.__http_request(f"{self.virtualization_api_base}/vms/{vm_resource.id}", HttpRequestType.DELETE, vm_resource)
        self.logger.success(f"Destroying VM {vm_resource.name} finished")

    def reboot_vm(self, vm_resource: VmResource, hard: bool = False):
        self.logger.info(f"Restarting VM {vm_resource.name}")
        self.__http_request(f"{self.virtualization_api_base}/vms/{vm_resource.id}/reboot", HttpRequestType.PUT, query_params={"hard": hard})
        self.logger.success(f"Restarting VM {vm_resource.name} finished")

    def check_vm_status(self, vm_resource: VmResource) -> VmStatus:
        self.logger.info(f"Checking status of VM {vm_resource.name}")
        vm_status = self.__http_request_get(f"{self.virtualization_api_base}/vms/{vm_resource.id}/status")
        self.logger.info(f"VM {vm_resource.name} status: {vm_status}")
        return VmStatus.model_validate(vm_status)

    def final_cleanup(self):
        self.logger.info(f"Requesting final cleanup of {self.blueprint_id}")
        self.__http_request(f"{self.rg_api_base}", HttpRequestType.DELETE)
        self.logger.success(f"Final cleanup of {self.blueprint_id} finished")
