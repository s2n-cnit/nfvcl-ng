from fastapi import APIRouter, status, Body
from pydantic import BaseModel

from blueprints_ng.providers.configurators.ansible_utils import run_ansible_playbook

ansible_router = APIRouter(
    prefix="/v1/ansible",
    tags=["Ansible"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


class AnsibleRestAnswer202(BaseModel):
    description: str = 'operation submitted'
    status: str = 'submitted'


@ansible_router.post("/run_playbook", response_model=AnsibleRestAnswer202)
async def run_playbook(host: str, username: str, password: str, payload: str = Body(None, media_type="application/yaml")):
    run_ansible_playbook(host, username, password, payload)
    return AnsibleRestAnswer202()
