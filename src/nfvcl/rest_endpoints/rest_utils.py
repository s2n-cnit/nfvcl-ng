from pathlib import Path
from threading import Thread
from fastapi import APIRouter, status, Body, Query, HTTPException
from starlette.responses import PlainTextResponse
from typing_extensions import Annotated
from pydantic import BaseModel
from nfvcl.blueprints_ng.lcm.blueprint_manager import get_blueprint_manager
from nfvcl.blueprints_ng.resources import VmResource
from nfvcl.models.config_model import NFVCLConfigModel
from nfvcl.utils.log import LOG_FILE_PATH
from nfvcl.utils.util import IP_PORT_PATTERN
from nfvcl.blueprints_ng.providers.configurators.ansible_utils import run_ansible_playbook
from nfvcl.utils.util import get_nfvcl_config

ansible_router = APIRouter(
    prefix="/v2/utils",
    tags=["Utils"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


class AnsibleRestAnswer(BaseModel):
    description: str = 'operation submitted'
    status: str = 'submitted'
    status_code: int = 202 # OK


@ansible_router.post("/ansible/run_playbook", response_model=AnsibleRestAnswer)
async def run_playbook(host: str, username: str, password: str, payload: str = Body(None, media_type="application/yaml")):
    """
    Allows running an ansible playbook on a remote host. The host does not need to be managed by nfvcl.

    Args:

        host: The host on witch the playbook is applied

        username: The username to be used to login on the remote target

        password: The password to be used to login on the remote target

        payload: The ansible playbook in yaml format to be applied on the remote target
    """
    thread = Thread(target=run_ansible_playbook, args=(host, username, password, payload))
    thread.start()
    return AnsibleRestAnswer()


@ansible_router.post("/ansible/rtr_request", response_model=AnsibleRestAnswer)
async def run_playbook(target: Annotated[str, Query(pattern=IP_PORT_PATTERN)], service: str, actionType: str, actionID: str, payload: str = Body(None, media_type="application/yaml")):
    """
    Integration for NEPHELE Project. Allow applying mitigation action on a target managed by the NFVCL (ePEM).
    Allows running an ansible playbook on a remote host. The host NEEDS to be managed by nfvcl.

    Args:

        target: The host on witch the playbook is applied ('host:port' format)

        payload: The ansible playbook in yaml format to be applied on the remote target
    """
    bm = get_blueprint_manager()
    target_ip = target.split(":")[0]
    vm: VmResource = bm.get_vm_target_by_ip(target_ip)
    if vm is None:
        # TODO post to DOC module
        return AnsibleRestAnswer(description="The Target has not been found in VMs managed by the NFVCL, the request will be forwarded to DOC module.", status="forwarded", status_code=404)
    else:
        ansible_runner_result, fact_cache = run_ansible_playbook(target_ip, vm.username, vm.password, payload)
        if ansible_runner_result.status == "failed":
            raise HTTPException(status_code=500, detail="Execution of Playbook failed. See NFVCL DEBUG log for more info.")
        return AnsibleRestAnswer(description="Playbook applied", status="success")

@ansible_router.get("/logs", response_class=PlainTextResponse)
async def logs():
    """
    Return logs from the log file to enable access though the web browser
    """
    nfvcl_config: NFVCLConfigModel = get_nfvcl_config()
    if nfvcl_config.log_level <= 10:  # 20 = INFO, DEBUG = 10
        log_file = Path(LOG_FILE_PATH)
        if log_file.exists() and log_file.is_file():
            return log_file.read_text()
        else:
            return f"File {log_file.absolute()} does not exist"
    else:
        return f"Log level({nfvcl_config.log_level}) is higher than DEBUG(10), HTML logging is disabled."
