from __future__ import annotations

from typing import List

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel


class AmfConfig(NFVCLBaseModel):
    address: str
    port: int


class Slice(NFVCLBaseModel):
    sst: int
    sd: int


class GNBConfig(NFVCLBaseModel):
    mcc: str
    mnc: str
    nci: str
    id_length: int = Field(..., alias='idLength')
    tac: int
    link_ip: str = Field(..., alias='linkIp')
    ngap_ip: str = Field(..., alias='ngapIp')
    gtp_ip: str = Field(..., alias='gtpIp')
    amf_configs: List[AmfConfig] = Field(..., alias='amfConfigs')
    slices: List[Slice]
    ignore_stream_ids: bool = Field(..., alias='ignoreStreamIds')
