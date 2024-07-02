from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class UacAic(BaseModel):
    mps: bool
    mcs: bool


class UacAcc(BaseModel):
    normal_class: int = Field(..., alias='normalClass')
    class11: bool
    class12: bool
    class13: bool
    class14: bool
    class15: bool


class Slice(BaseModel):
    sst: int
    sd: int


class Session(BaseModel):
    type: str
    apn: str
    slice: Slice


class ConfiguredNssaiItem(BaseModel):
    sst: int
    sd: int


class DefaultNssaiItem(BaseModel):
    sst: int
    sd: int


class Integrity(BaseModel):
    ia1: bool = Field(..., alias='IA1')
    ia2: bool = Field(..., alias='IA2')
    ia3: bool = Field(..., alias='IA3')


class Ciphering(BaseModel):
    ea1: bool = Field(..., alias='EA1')
    ea2: bool = Field(..., alias='EA2')
    ea3: bool = Field(..., alias='EA3')


class IntegrityMaxRate(BaseModel):
    uplink: str
    downlink: str


class UEConfig(BaseModel):
    supi: str
    mcc: str
    mnc: str
    protection_scheme: int = Field(..., alias='protectionScheme')
    home_network_public_key: str = Field(..., alias='homeNetworkPublicKey')
    home_network_public_key_id: int = Field(..., alias='homeNetworkPublicKeyId')
    routing_indicator: str = Field(..., alias='routingIndicator')
    key: str
    op: str
    op_type: str = Field(..., alias='opType')
    amf: str
    imei: str
    imei_sv: str = Field(..., alias='imeiSv')
    gnb_search_list: List[str] = Field(..., alias='gnbSearchList')
    uac_aic: UacAic = Field(..., alias='uacAic')
    uac_acc: UacAcc = Field(..., alias='uacAcc')
    sessions: List[Session]
    configured_nssai: List[ConfiguredNssaiItem] = Field(..., alias='configured-nssai')
    default_nssai: List[DefaultNssaiItem] = Field(..., alias='default-nssai')
    integrity: Integrity
    ciphering: Ciphering
    integrity_max_rate: IntegrityMaxRate = Field(..., alias='integrityMaxRate')
