from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel


class Network(NFVCLBaseModel):
    name: str
    cidr: str
    gateway: Optional[str] = Field(default=None)


class Networks(NFVCLBaseModel):
    mgmt: Network
    data: Network
    gnb: Network
    n3: Network
    n6: Network
    k8s_lb_ips: List[str]

class Vim(NFVCLBaseModel):
    tenant: str
    user: str
    password: str
    url: str


class Config(NFVCLBaseModel):
    networks: Networks
    vim: Vim


class ConfigUniteTest(NFVCLBaseModel):
    config: Config
