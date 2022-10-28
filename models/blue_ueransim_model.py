from __future__ import annotations
from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, constr, conlist


class ConfiguredNssaiItem(BaseModel):
    sst: int


class DefaultNssaiItem(BaseModel):
    sst: int
    sd: int


class Slice(BaseModel):
    sst: int
    sd: int


class PDUSessionType(Enum):
    IPv4 = 'IPv4'
    IPv6 = 'IPv6'


class Session(BaseModel):
    type: PDUSessionType
    apn: str
    slice: Slice

    class Config:
        use_enum_values = True


class OpType(Enum):
    OPC = 'OPC'


class Sim(BaseModel):
    imsi: constr(regex=r'^[0-9]*$', min_length=15, max_length=15)
    plmn: constr(regex=r'^[0-9]*$', min_length=5, max_length=5)
    key: constr(regex=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    op: constr(regex=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    opType: OpType
    amf: Optional[constr(min_length=4, max_length=4)] = None
    configured_nssai: Optional[List[ConfiguredNssaiItem]] = Field(None, min_items=1)
    default_nssai: Optional[List[DefaultNssaiItem]] = Field(None, min_items=1)
    sessions: Optional[List[Session]] = Field(None, min_items=1)

    class Config:
        use_enum_values = True


class Ue(BaseModel):
    id: Optional[int] = Field(None, description='UE identifier')
    sims: Optional[List[Sim]] = Field(
        None, description='list of sims in the current UE virtual machine'
    )


class UeranSimNetworkEndPoints(BaseModel):
    mgt: str = Field(
        ..., description='name of the topology network to be used for management'
    )
    wan: str = Field(
        ...,
        description='name of the topology network to be used by NodeBs to attach the core network',
    )


class AreaInfo(BaseModel):
    id: int = Field(..., description='Area identifier, it will be used as TAC in the NodeB configuration')
    nci: Optional[str] = Field(None, description='gNodeB nci identifier')
    idLength: Optional[int] = Field(None, description='gNodeB nci identifier length')
    ues: List[Ue] = Field(
        ..., description='list of virtual UEs to be instantiated'
    )


class UeranSimConfig(BaseModel):
    network_endpoints: UeranSimNetworkEndPoints


class UeranSimBlueprintRequestInstance(BaseModel):
    type: Literal["UeRanSim"]
    config: UeranSimConfig
    areas: conlist(AreaInfo, min_items=1) = Field(
        ...,
        description='list of areas to instantiate the Blueprint',
    )

    class Config:
        use_enum_values = True
