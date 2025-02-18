from __future__ import annotations

from typing import List

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel


class UacAic(NFVCLBaseModel):
    mps: bool
    mcs: bool


class UacAcc(NFVCLBaseModel):
    normal_class: int = Field(..., alias='normalClass')
    class11: bool
    class12: bool
    class13: bool
    class14: bool
    class15: bool


class Slice(NFVCLBaseModel):
    sst: int
    sd: int


class Session(NFVCLBaseModel):
    type: str
    apn: str
    slice: Slice


class ConfiguredNssaiItem(NFVCLBaseModel):
    sst: int
    sd: int


class DefaultNssaiItem(NFVCLBaseModel):
    sst: int
    sd: int


class Integrity(NFVCLBaseModel):
    ia1: bool = Field(..., alias='IA1')
    ia2: bool = Field(..., alias='IA2')
    ia3: bool = Field(..., alias='IA3')


class Ciphering(NFVCLBaseModel):
    ea1: bool = Field(..., alias='EA1')
    ea2: bool = Field(..., alias='EA2')
    ea3: bool = Field(..., alias='EA3')


class IntegrityMaxRate(NFVCLBaseModel):
    uplink: str
    downlink: str


class UEConfig(NFVCLBaseModel):
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
