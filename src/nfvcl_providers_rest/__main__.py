import inspect
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from typing import List, Optional, Callable, Dict

import uvicorn
from fastapi import FastAPI, APIRouter

from nfvcl_core_models.vim.vim_models import VimModel
from nfvcl_providers.vim_clients.openstack_vim_client import OpenStackVimClient
from pydantic import Field
from starlette import status
from starlette.requests import Request
from starlette.responses import Response
from verboselogs import VerboseLogger

from nfvcl_common.utils.log import mod_logger, create_logger, set_log_level  # Order 1
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.config import NFVCLConfigModel, load_nfvcl_config  # Order 1
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address
from nfvcl_core_models.pre_work import PreWorkCallbackResponse
from nfvcl_core_models.resources import VmResource, NetResourcePool, NetResource
from nfvcl_core_models.response_model import OssCompliantResponse
from nfvcl_core_models.task import NFVCLTask, NFVCLTaskResult, NFVCLTaskStatus, NFVCLTaskStatusType
from nfvcl_providers.virtualization.openstack.virtualization_provider_openstack import VirtualizationProviderOpenstack

#### BEFORE IMPORTING ANYTHING FROM NFVCL() main file ####
nfvcl_rest_config: NFVCLConfigModel

def load_configuration():
    config_path = os.getenv("NFVCL_CONFIG_PATH")
    if config_path:
        if Path(config_path).is_file():
            config = load_nfvcl_config(config_path)
        else:
            logger.error(f"NFVCL_CONFIG_PATH is set to {config_path} but the file does not exist, loading from default location.")
            config = load_nfvcl_config()
    else:
        config = load_nfvcl_config()

    return config

nfvcl_rest_config = load_configuration()
set_log_level(nfvcl_rest_config.log_level)

########### VARS ############
app: FastAPI
logger: VerboseLogger = create_logger("NFVCL_PROVIDERS")


@asynccontextmanager
async def lifespan(fastapp: FastAPI):
    """
    Mod the unicorn loggers to add colors and custom style
    """
    mod_logger(logging.getLogger('uvicorn'), remove_handlers=True, disable_propagate=True)
    mod_logger(logging.getLogger('uvicorn.access'), remove_handlers=True, disable_propagate=True)
    mod_logger(logging.getLogger('uvicorn.error'), remove_handlers=True, disable_propagate=True)
    mod_logger(logging.getLogger('fastapi'), remove_handlers=True, disable_propagate=True)
    yield
    # If something need to be done after shutdown of the app, it can be done here.



def readiness():
    """
    Readiness check for the NFVCL
    """
    return Response(status_code=status.HTTP_200_OK)


class VmResourceAnsibleConfigurationSerialized(NFVCLBaseModel):
    access_ip: SerializableIPv4Address = Field()
    username: str = Field()
    password: str = Field()
    ansible_playbook: str = Field()

class NetPayload(NFVCLBaseModel):
    net_name: str = Field()
    cidr: str = Field()
    allocation_pool: Optional[NetResourcePool] = Field(default=None, description="Allocation Pool for the network, used to allocate IPs from the network")

class AttachNetPayload(NFVCLBaseModel):
    net_name: str = Field()

def callback_function(event: threading.Event, namespace: Dict, msg: NFVCLTaskResult):
    namespace["msg"] = msg
    event.set()


def pre_work_callback_function(event: threading.Event, namespace: Dict, msg: PreWorkCallbackResponse):
    namespace["msg"] = msg
    event.set()

def testtttt(vm_id: str) -> str:
    time.sleep(20)
    return "test" + vm_id



class NFVCLProviderResourceGroup(NFVCLBaseModel):
    id: str = Field()
    vms: Dict[str, VmResource] = Field()
    nets: Dict[str, NetResource] = Field()


class NFVCLProviderAgent(NFVCLBaseModel):
    uuid: str = Field()
    resource_groups: Dict[str, str] = Field()

class NFVCLProviderDatabase(NFVCLBaseModel):
    agents: Dict[str, NFVCLProviderAgent] = Field(default_factory=dict)



class VirtualizationProviderApiRouter:
    def __init__(self, name: str):
        self.name = name
        self.router = APIRouter(prefix=f"/{name}/virtualization")
        self.vms_router = APIRouter(prefix="/vms")
        self.resource_group_router = APIRouter(prefix="/rg")
        self.net_router = APIRouter(prefix="/nets")
        self.task_router = APIRouter(prefix="/tasks")

        self.vms_router.add_api_route("/", self.create_vm, methods=["POST"])
        self.vms_router.add_api_route("/", self.list_vms, methods=["GET"])
        self.vms_router.add_api_route("/{vm_id}", self.vm_info, methods=["GET"])
        self.vms_router.add_api_route("/{vm_id}", self.destroy_vm, methods=["DELETE"])
        self.vms_router.add_api_route("/{vm_id}/configure", self.configure_vm, methods=["PUT"])
        self.vms_router.add_api_route("/{vm_id}/reboot", self.reboot_vm, methods=["PUT"])

        self.vms_router.add_api_route("/{vm_id}/net", self.attach_net, methods=["POST"])
        self.vms_router.add_api_route("/{vm_id}/net", self.list_attached_nets, methods=["GET"])
        self.vms_router.add_api_route("/{vm_id}/net/{net_name}", self.detach_net, methods=["DELETE"])

        self.net_router.add_api_route("/", self.create_net, methods=["POST"])
        self.net_router.add_api_route("/", self.list_nets, methods=["GET"])
        self.net_router.add_api_route("/{net_name}", self.net_info, methods=["GET"])
        self.net_router.add_api_route("/{net_name}", self.destroy_net, methods=["DELETE"])

        self.task_router.add_api_route("/{task_id}", self.get_task_status, methods=["GET"])

        self.resource_group_router.add_api_route("/{rg_id}", self.get_rg, methods=["GET"])
        self.resource_group_router.add_api_route("/{rg_id}", self.delete_rg, methods=["DELETE"])

        self.router.include_router(self.resource_group_router)
        self.router.include_router(self.vms_router)
        self.router.include_router(self.net_router)
        self.router.include_router(self.task_router)

        def dummy_persistence_function():
            pass

        self.provider = VirtualizationProviderOpenstack(1, "TEST", vim_client=OpenStackVimClient(VimModel.model_validate_json(
            """
            {
      "name": "oslab",
      "vim_type": "openstack",
      "vim_url": "http://os-lab.maas:5000/v3",
      "vim_user": "alderico",
      "vim_password": "pippo00",
      "vim_timeout": null,
      "ssh_keys": [
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCoLpF23Q517q0aHM3KRVsZuzcPqM9gsymvZNUWoaI0Xi01lG5xDL5fJlfJXJKl8rkAe/L1RV/1lj4nFFcClKX84uVlhBO4TMLrLbZCC4JJeMPofnMGNqiK4HanbUPzzmuYowbnPXmard9UNsyyHnTUxy7q6rPblFe0ZsFiLTz/CBBXdL0oID1miCd42jNqaMqiMMyFhIob6CyzBPTW5YEI4vd0/eTWO9IyHN4YuYnnM+ESDs1yTQjQHS4b5LdQ04dWJRWZWwP4QoJapge6kqV5vvZl3HaGyiN4Zn/rNGSAtJs8f5OxvDNixE+9yWOELyIfYCH/lib9Yxw6jUkrelE6h8ovrdFfm0HGjctspoCf9ZncWP5jZqQOeBg7WBicPHulE9fFI8b81csbK1gN2/WK4hftTy4U40Ki/DKf6Bh+uEykXa9xJgpJFW+EAoGMrtT6i20Ho6lx6Xz2cEE8phTVFF6B7mjF5q6A0dlyypHJcBN/R6FgXO/AevKQ6uvlPQU= alderico@DESKTOP-2I40FIJ"
      ],
      "vim_openstack_parameters": {
        "region_name": "RegionOne",
        "project_name": "alderico",
        "user_domain_name": "Default",
        "project_domain_name": "Default"
      },
      "vim_proxmox_parameters": {
        "proxmox_realm": "pam",
        "proxmox_node": null,
        "proxmox_images_volume": "local",
        "proxmox_vm_volume": "local-lvm",
        "proxmox_token_name": "",
        "proxmox_token_value": "",
        "proxmox_otp_code": "",
        "proxmox_privilege_escalation": "none"
      },
      "config": {
        "insecure": true,
        "APIversion": "v3.3",
        "use_floating_ip": false
      },
      "networks": [
        "dmz-internal",
        "alderico-net"
      ],
      "routers": [],
      "areas": [
        0,
        1,
        2,
        3,
        4,
        1001,
        1002,
        1003,
        1004
      ]
    }
            """
        )), persistence_function=dummy_persistence_function)

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

    def get_task_status(self, task_id: str, request: Request) -> NFVCLTaskStatus:
        if task_id not in self.task_manager.task_history:
            raise Exception(f"Task {task_id} not found")
        task = self.task_manager.task_history[task_id]
        if task.result is None:
            return NFVCLTaskStatus(task_id=task_id, status=NFVCLTaskStatusType.RUNNING)
        else:
            return NFVCLTaskStatus(task_id=task_id, status=NFVCLTaskStatusType.DONE, result=task.result.result, error=task.result.error, exception=str(task.result.exception) if task.result.exception else None)

    def get_rg(self, rg_id: str, request: Request):
        pass

    def delete_rg(self, rg_id: str, request: Request):
        pass

    def create_vm(self, vm_resource: VmResource, request: Request):
        return self.provider.create_vm(vm_resource)


    def list_vms(self, request: Request):
        pass

    def vm_info(self, vm_id: str, request: Request):
        return self._add_task_sync(testtttt, vm_id=vm_id)

    def destroy_vm(self, vm_id: str, request: Request):
        return self.provider.destroy_vm(vm_id)

    def configure_vm(self, vm_id: str, vm_resource_configuration: VmResourceAnsibleConfigurationSerialized, request: Request) -> dict:
        return {"aa": vm_id}

    def reboot_vm(self, vm_id: str, request: Request, hard: bool = False):
        pass

    def attach_net(self, vm_id: str, body: AttachNetPayload, request: Request):
        pass

    def list_attached_nets(self, vm_id: str, request: Request) -> List[NetPayload]:
        pass

    def detach_net(self, vm_id: str, net_name: str, request: Request):
        pass

    def create_net(self, net_resource: NetPayload, request: Request):
        pass

    def list_nets(self, request: Request) -> List[NetPayload]:
        pass

    def net_info(self, net_name: str, request: Request) -> NetPayload:
        pass

    def destroy_net(self, net_name: str, request: Request):
        pass

    def final_cleanup(self, request: Request):
        pass

if __name__ == "__main__":

    hello = VirtualizationProviderApiRouter("os-lab")
    app = FastAPI(
        title="NFVCL Provider Server",
        description="CNIT/UniGe S2N Lab NFVCL Provider Server",
        # version=global_ref.nfvcl_config.nfvcl.version,
        license_info={
            "name": "Apache 2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
        swagger_ui_parameters={"syntaxHighlight.theme": "obsidian", "deepLinking": True},
        lifespan=lifespan,
        ignore_trailing_slash=True,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    # app.add_middleware(ExceptionMiddleware)
    app.include_router(hello.router)

    uvicorn.run(app, host=nfvcl_rest_config.nfvcl.ip, port=nfvcl_rest_config.nfvcl.port)
