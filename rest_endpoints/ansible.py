from threading import Thread
from typing import Union
from fastapi import APIRouter, status, Body, Query, HTTPException
from typing_extensions import Annotated
from pydantic import BaseModel

from blueprints_ng.lcm.blueprint_manager import BlueprintManager
from blueprints_ng.resources import VmResource
from rest_endpoints.blue_ng_router import get_blueprint_manager
from utils.util import IP_PORT_PATTERN

from blueprints_ng.providers.configurators.ansible_utils import run_ansible_playbook

ansible_router = APIRouter(
    prefix="/v1/ansible",
    tags=["Ansible"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


class AnsibleRestAnswer(BaseModel):
    description: str = 'operation submitted'
    status: str = 'submitted'
    status_code: int = 202 # OK


@ansible_router.post("/run_playbook", response_model=AnsibleRestAnswer)
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
