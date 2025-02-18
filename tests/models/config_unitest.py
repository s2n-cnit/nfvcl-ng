from __future__ import annotations

from nfvcl_core_models.base_model import NFVCLBaseModel


class Networks(NFVCLBaseModel):
    mgmt: str
    data: str
    k8s_controller: str


class Vim(NFVCLBaseModel):
    user: str
    password: str
    url: str


class Config(NFVCLBaseModel):
    networks: Networks
    vim: Vim


class ConfigUniteTest(NFVCLBaseModel):
    config: Config
