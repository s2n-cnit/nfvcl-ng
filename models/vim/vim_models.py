from enum import Enum
from typing import List

from pydantic import BaseModel, HttpUrl, Field


class VimTypeEnum(str, Enum):
    openstack: str = 'openstack'

class VimModel(BaseModel):
    class VimConfigModel(BaseModel):
        # class VimAdditionalProperties(BaseModel):
        insecure: bool = True
        APIversion: str = 'v3.3'
        use_floating_ip: bool = False
        # additionalProp1: VimAdditionalProperties

    name: str
    vim_type: VimTypeEnum = 'openstack'
    schema_version: str = '1.3'
    vim_url: HttpUrl
    vim_tenant_name: str = 'admin'
    vim_user: str = 'admin'
    vim_password: str = 'admin'
    config: VimConfigModel = {'additionalProp1': {'insecure': True, 'APIversion': 'v3.3'}}
    networks: List[str] = []
    routers: List[str] = []
    areas: List[int] = []

class UpdateVimModel(BaseModel):
    name: str
    networks_to_add: List[str] = Field(
        [],
        description="List of network names declared in the topology to be added to the VIM"
    )
    networks_to_del: List[str] = Field(
        [],
        description="List of network names declared in the topology to be deleted to the VIM"
    )
    routers_to_add: List[str] = Field(
        [],
        description="List of router names declared in the topology to be added to the VIM"
    )
    routers_to_del: List[str] = Field(
        [],
        description="List of router names declared in the topology to be added to the VIM"
    )
    areas_to_add: List[str] = Field(
        [],
        description="List of served area identifiers declared in the topology to be added to the VIM"
    )
    areas_to_del: List[str] = Field(
        [],
        description="List of served area identifiers declared in the topology to be added to the VIM"
    )