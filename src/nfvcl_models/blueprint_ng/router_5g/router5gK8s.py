

from typing import List, Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel


class Route(NFVCLBaseModel):
    to: str
    via: str


class Interface(NFVCLBaseModel):
    name: str
    ip: str
    iface: str


class Router(NFVCLBaseModel):
    deploy: bool
    cni: Optional[str] = Field(default="macvlan")
    resource_name: str = Field(..., alias='resourceName')
    routes: List[Route]
    interfaces: List[Interface]


class Config(NFVCLBaseModel):
    router: Router


class Router5GK8s(NFVCLBaseModel):
    config: Optional[Config] = None
