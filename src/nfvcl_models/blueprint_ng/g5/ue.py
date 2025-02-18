from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import Field, model_validator, AliasChoices

from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPoint, NetworkEndPointWithType
from nfvcl_models.blueprint_ng.g5.common5g import Slice5G
from nfvcl_models.blueprint_ng.g5.custom_types_5g import IMSIType, PLMNType, KEYType, OPCType, PDUSessionType, DNNType
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core_models.custom_types import AreaIDType, IPHostType

class UESession(NFVCLBaseModel):
    type: PDUSessionType
    dnn: DNNType = Field(validation_alias=AliasChoices("dnn", "apn"))
    slice: Slice5G

class OpType(Enum):
    OPC = 'OPC'

class UESim(NFVCLBaseModel):
    imsi: IMSIType = Field()
    plmn: PLMNType = Field()
    key: KEYType = Field()
    op: OPCType = Field()
    opType: OpType = Field()
    amf: Optional[int] = Field(default=None)
    configured_nssai: Optional[List[Slice5G]] = Field(default=None, min_length=1)
    default_nssai: Optional[List[Slice5G]] = Field(default=None, min_length=1)
    sessions: Optional[List[UESession]] = Field(default=None, min_length=1)

class BlueCreateModelNetworks(NFVCLBaseModel):
    mgt: Optional[NetworkEndPoint] = Field(default=None, description="Management network, only used when the UE is a VM")
    ru1: Optional[NetworkEndPointWithType] = Field(default=None, description="Radio network, only used when the UE need to connect to a simulated radio")

class USRPType(str, Enum):
    RFSIM = "rfsim" # The radio will be emulated
    B2XX = "b2xx"   # USRP b2xx series, USB connection
    N3XX = "n3xx"   # USRP n3xx series, Network connection
    X3XX = "x3xx"   # USRP x3xx series, Network connection

class UEBlueCreateModelGeneric(BlueprintNGCreateModel):
    area_id: AreaIDType = Field(description="The area in which the UE will be deployed")
    networks: BlueCreateModelNetworks = Field(description="Networks to be used by the UE")
    gnb_host: Optional[IPHostType] = Field(default=None, description="IP of the gNB to connect to, only used when the UE need to connect to a simulated radio")
    usrp: Optional[USRPType] = Field(default=None, description="USRP type to use, only needed in some implementations, if 'rfsim' is used the radio network and gnb_ip is also needed")
    sims: List[UESim] = Field(description="List of SIMs to be used by the UE", min_length=1)

    @model_validator(mode='after')
    def validate_atts(self):
        if self.usrp == USRPType.RFSIM:
            if self.networks.ru1 is None:
                raise ValueError("Radio network (ru1) is needed when using usrp: rfsim")
            if self.gnb_host is None:
                raise ValueError("gNB IP is needed when using usrp: rfsim")
        return self

