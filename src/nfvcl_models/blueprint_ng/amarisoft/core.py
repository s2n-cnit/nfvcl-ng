from __future__ import annotations

from typing import Union, Optional
from pydantic import BaseModel, Field

from nfvcl_models.blueprint_ng.g5.custom_types_5g import SSTType, SDType


class PreEmption:
    CAPABILITY = "shall_not_trigger_pre_emption"
    VULNERABILITY = "not_pre_emptable"


class ERAB(BaseModel):
    qci: int = 9
    priority_level: int = 15
    pre_emption_capability: str = PreEmption.CAPABILITY
    pre_emption_vulnerability: str = PreEmption.VULNERABILITY


class SNSSAI(BaseModel):
    sst: SSTType
    sd: int | None = None


class QoSFlow(BaseModel):
    fiveqi: int = Field(alias="5qi", default=9)
    priority_level: int = 15
    pre_emption_capability: str = PreEmption.CAPABILITY
    pre_emption_vulnerability: str = PreEmption.VULNERABILITY

    model_config = {"populate_by_name": True}


class PdnSlice(BaseModel):
    snssai: SNSSAI
    qos_flows: list[QoSFlow]


class PDNConfig(BaseModel):
    pdn_type: str = "ipv4"
    access_point_name: str | None = None
    first_ip_addr: str | None = None
    last_ip_addr: str | None = None
    ip_addr_shift: int | None = 1
    dns_addr: Union[str, list[str]] | None = None
    erabs: list[ERAB] = Field(default=[ERAB()])
    slices: Optional[list[PdnSlice]] = Field(default=None)
