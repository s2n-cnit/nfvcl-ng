import inspect
import threading
from functools import partial
from typing import Callable, Optional, Dict, Annotated, List

import urllib3
from dependency_injector.wiring import Provide

from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_common.utils.log import create_logger
from nfvcl_common.utils.nfvcl_public_utils import NFVCLPublicSectionModel, NFVCLPublic
from nfvcl_core.managers.task_manager import TaskManager
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.pre_work import PreWorkCallbackResponse
from nfvcl_core_models.resources import VmResource, NetResource
from nfvcl_core_models.response_model import OssCompliantResponse
from nfvcl_core_models.task import NFVCLTask, NFVCLTaskResult, NFVCLTaskStatus, NFVCLTaskStatusType
from nfvcl_core_models.vim.vim_models import VimModel
from nfvcl_providers_rest.config import NFVCLProvidersConfigModel
from nfvcl_providers_rest.database.agent_repository import NFVCLProviderAgentRepository
from nfvcl_providers_rest.database.vim_repository import NFVCLProviderVimRepository
from nfvcl_providers_rest.managers.admin_operations_manager import AdminOperationsManager
from nfvcl_providers_rest.managers.virtualization_manager import VirtualizationManager
from nfvcl_providers_rest.models.virtualization import VmResourceAnsibleConfigurationSerialized, AttachNetPayload, NetworkCheckPayload
from nfvcl_providers_rest.nfvcl_providers_container import NFVCLProvidersContainer

def callback_function(event: threading.Event, namespace: Dict, msg: NFVCLTaskResult):
    namespace["msg"] = msg
    event.set()


def pre_work_callback_function(event: threading.Event, namespace: Dict, msg: PreWorkCallbackResponse):
    namespace["msg"] = msg
    event.set()

class NFVCLProviders:
    RG_SECTION = NFVCLPublicSectionModel(name="Resource Groups", description="Operations related to the resource groups", path="/v1/rg")
    TASK_SECTION = NFVCLPublicSectionModel(name="Tasks", description="Operations related to the tasks", path="/v1/tasks")
    VIM_SECTION = NFVCLPublicSectionModel(name="VIMs", description="Operations related to VIMs", path="/v1/vims")

    def __init__(
        self,
        config: NFVCLProvidersConfigModel = Provide[NFVCLProvidersContainer.config],
        task_manager: TaskManager = Provide[NFVCLProvidersContainer.task_manager],
        agent_repository: NFVCLProviderAgentRepository = Provide[NFVCLProvidersContainer.agent_repository],
        vim_repository: NFVCLProviderVimRepository = Provide[NFVCLProvidersContainer.vim_repository],
        virtualization_manager: VirtualizationManager = Provide[NFVCLProvidersContainer.virtualization_manager],
        admin_operations_manager: AdminOperationsManager = Provide[NFVCLProvidersContainer.admin_operations_manager]
    ):
        self.logger = create_logger(self.__class__.__name__)
        self.config = NFVCLProvidersConfigModel.model_validate(config)
        self.task_manager = task_manager
        self.agent_repository = agent_repository
        self.vim_repository = vim_repository
        self.virtualization_manager = virtualization_manager
        self.admin_operations_manager = admin_operations_manager
        urllib3.disable_warnings()

    def get_ordered_public_methods(self) -> List[Callable]:
        """
        Get the list of all public methods that should be exposed by the NFVCL
        Returns: List of public methods callable
        """
        public_methods = []
        for attr in dir(self):
            if callable(getattr(self, attr)) and hasattr(getattr(self, attr), "nfvcl_public"):
                public_methods.append(getattr(self, attr))

        return sorted(public_methods, key=lambda x: x.order)

    def _add_task_sync(self, function: Callable, *args, **kwargs):
        event = threading.Event()
        # used to receive the return data from the function
        namespace = {}
        self.task_manager.add_task(NFVCLTask(function, partial(callback_function, event, namespace), *args, **kwargs))
        event.wait()
        task_result: NFVCLTaskResult = namespace["msg"]
        if task_result.error:
            raise task_result.exception
        return namespace["msg"]

    def _add_task_async(self, function: Callable, *args, **kwargs) -> OssCompliantResponse:
        callback: Optional[Callable] = kwargs.pop("callback", None)
        # check if the callable function has a pre_work_callback parameter
        function_args = inspect.getfullargspec(function).args
        event: Optional[threading.Event] = None
        namespace = {}

        if "pre_work_callback" in function_args:
            event = threading.Event()
            kwargs["pre_work_callback"] = partial(pre_work_callback_function, event, namespace)

        task_id = self.task_manager.add_task(NFVCLTask(function, callback, *args, **kwargs))

        async_response: OssCompliantResponse

        if "pre_work_callback" in function_args and event:
            event.wait()
            pre_work_callback_response: PreWorkCallbackResponse = namespace["msg"]
            async_response = pre_work_callback_response.async_return
        else:
            async_response = OssCompliantResponse(detail="Operation submitted")

        async_response.task_id = task_id

        return async_response

    def add_task(self, function, *args, **kwargs):
        callback: Optional[Callable] = kwargs.pop("callback", None)

        # TODO check if the function is sync or async
        if callback is None:
            return self._add_task_sync(function, *args, **kwargs).result
        else:
            return self._add_task_async(function, *args, **kwargs, callback=callback)

    @NFVCLPublic(path="/{task_id}", section=TASK_SECTION, method=HttpRequestType.GET, sync=True)
    def get_task_status(self, task_id: str) -> NFVCLTaskStatus:
        """
        Get the status of a task given its task_id

        Warnings:
            If NFVCL is restarted the task_id will be lost and the task will not be found
        Args:
            task_id: ID of the task to get the status of

        Returns: NFVCLTaskStatus, the "status" field can be "running" or "done"
        """
        if task_id not in self.task_manager.task_history:
            raise NFVCLCoreException(message="Task id not found", http_equivalent_code=404)
        else:
            task = self.task_manager.task_history[task_id]
            if task.result is None:
                return NFVCLTaskStatus(task_id=task_id, status=NFVCLTaskStatusType.RUNNING)
            else:
                return NFVCLTaskStatus(task_id=task_id, status=NFVCLTaskStatusType.DONE, result=task.result.result, error=task.result.error, exception=str(task.result.exception) if task.result.exception else None)

    @NFVCLPublic(path="/", section=VIM_SECTION, method=HttpRequestType.POST, sync=True)
    def add_vim(self, vim: VimModel, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.admin_operations_manager.add_vim, vim, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}", section=VIM_SECTION, method=HttpRequestType.DELETE)
    def delete_rg(self, vim_name: str, resource_group_id: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.virtualization_manager.final_cleanup, vim_name, resource_group_id, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/check_networks", section=VIM_SECTION, method=HttpRequestType.POST)
    def check_networks(self, vim_name: str, resource_group_id: str, network_check_payload: NetworkCheckPayload, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.virtualization_manager.check_networks, vim_name, resource_group_id, network_check_payload, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/vms/", section=VIM_SECTION, method=HttpRequestType.POST)
    def create_vm(self, vim_name: str, resource_group_id: str, vm_resource: VmResource, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.virtualization_manager.create_vm, vim_name, resource_group_id, vm_resource, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/vms/", section=VIM_SECTION, method=HttpRequestType.GET, sync=True)
    def list_vms(self, vim_name: str, resource_group_id: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.virtualization_manager.list_vms, vim_name, resource_group_id, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/vms/{vm_id}", section=VIM_SECTION, method=HttpRequestType.GET, sync=True)
    def vm_info(self, vim_name: str, resource_group_id: str, vm_id: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.virtualization_manager.vm_info, vim_name, resource_group_id, vm_id, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/vms/{vm_id}/status", section=VIM_SECTION, method=HttpRequestType.GET, sync=True)
    def vm_status(self, vim_name: str, resource_group_id: str, vm_id: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.virtualization_manager.vm_status, vim_name, resource_group_id, vm_id, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/vms/{vm_id}", section=VIM_SECTION, method=HttpRequestType.DELETE)
    def destroy_vm(self, vim_name: str, resource_group_id: str, vm_id: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.virtualization_manager.destroy_vm, vim_name, resource_group_id, vm_id, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/vms/{vm_id}/configure", section=VIM_SECTION, method=HttpRequestType.PUT)
    def configure_vm(self, vim_name: str, resource_group_id: str, vm_id: str, vm_resource_configuration: VmResourceAnsibleConfigurationSerialized, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.virtualization_manager.configure_vm, vim_name, resource_group_id, vm_id, vm_resource_configuration, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/vms/{vm_id}/reboot", section=VIM_SECTION, method=HttpRequestType.PUT)
    def reboot_vm(self, vim_name: str, resource_group_id: str, vm_id: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], hard: bool = False, callback=None):
        return self.add_task(self.virtualization_manager.reboot_vm, vim_name, resource_group_id, vm_id, agent_uuid, hard=hard, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/vms/{vm_id}/net", section=VIM_SECTION, method=HttpRequestType.POST)
    def attach_net(self, vim_name: str, resource_group_id: str, vm_id: str, body: AttachNetPayload, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.virtualization_manager.attach_net, vim_name, resource_group_id, vm_id, body, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/vms/{vm_id}/net", section=VIM_SECTION, method=HttpRequestType.GET, sync=True)
    def list_attached_nets(self, vim_name: str, resource_group_id: str, vm_id: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None) -> List[NetResource]:
        return self.add_task(self.virtualization_manager.list_attached_nets, vim_name, resource_group_id, vm_id, agent_uuid, callback=callback)

    # @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/vms/{vm_id}/net/{net_name}", section=VIM_SECTION, method=HttpRequestType.DELETE)
    # def detach_net(self, vim_name: str, resource_group_id: str, vm_id: str, net_name: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"]):
    #     pass

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/nets", section=VIM_SECTION, method=HttpRequestType.POST)
    def create_net(self, vim_name: str, resource_group_id: str, net_resource: NetResource, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None):
        return self.add_task(self.virtualization_manager.create_net, vim_name, resource_group_id, net_resource, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/nets", section=VIM_SECTION, method=HttpRequestType.GET, sync=True)
    def list_nets(self, vim_name: str, resource_group_id: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None) -> List[NetResource]:
        return self.add_task(self.virtualization_manager.list_nets, vim_name, resource_group_id, agent_uuid, callback=callback)

    @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/nets/{net_name}", section=VIM_SECTION, method=HttpRequestType.GET, sync=True)
    def net_info(self, vim_name: str, resource_group_id: str, net_name: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"], callback=None) -> NetResource:
        return self.add_task(self.virtualization_manager.net_info, vim_name, resource_group_id, net_name, agent_uuid, callback=callback)

    # @NFVCLPublic(path="/{vim_name}/{resource_group_id}/virtualization/nets/{net_name}", section=VIM_SECTION, method=HttpRequestType.DELETE)
    # def destroy_net(self, vim_name: str, resource_group_id: str, net_name: str, agent_uuid: Annotated[str, "header/X-NFVCL-Agent-ID"]):
    #     pass

def configure_injection(nfvcl_config: NFVCLProvidersConfigModel):
    container = NFVCLProvidersContainer()
    container.config.from_pydantic(nfvcl_config)
    container.init_resources()
    container.wire(modules=[__name__, "nfvcl_core.managers"])
    # register_loader_containers(Container)
