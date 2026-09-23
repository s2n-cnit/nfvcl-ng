from enum import StrEnum
from typing import List, Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_models.blueprint_ng.g5.common5g import Slice5G
from nfvcl_models.blueprint_ng.g5.custom_types_5g import PLMNType, IMSIType, KEYType, OPCType, DNNType


class OPC(StrEnum):
    OPC = 'OPC'
    OP = 'OP'

class Enviroment(StrEnum):
    DOCKER = 'docker'
    INCUS = 'incus'

class UEPDUConfigure(NFVCLBaseModel):
    dnn: DNNType = Field(examples=["internet"])

    plmn: PLMNType = Field(examples=["00101"])
    tac: Optional[int] = Field(default=None)
    imsi: Optional[IMSIType] = Field(default=None)
    key: Optional[KEYType] = Field(default=None)
    opc: Optional[OPCType] = Field(default=None)
    opType: Optional[OPC] = Field(default=OPC.OPC)
    gnb_ip: Optional[str] = Field(default=None)
    nssai: Optional[List[Slice5G]] = Field(default_factory=list)
