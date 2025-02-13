from enum import Enum
from typing import List, Optional

from pydantic import Field, model_validator

from nfvcl.models.blueprint_ng.blueprint_ueransim_model import UeransimSim
from nfvcl.models.blueprint_ng.core5g.common import NetworkEndPoint, NetworkEndPointWithType
from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core.models.custom_types import AreaIDType, IPHostType


class BlueCreateModelNetworks(NFVCLBaseModel):
    mgt: Optional[NetworkEndPoint] = Field(default=None, description="Management network, only used when the UE is a VM")
    ru1: Optional[NetworkEndPointWithType] = Field(default=None, description="Radio network, only used when the UE need to connect to a simulated radio")

class USRPType(str, Enum):
    RFSIM = "rfsim" # The radio will be emulated
    B2XX = "b2xx"   # USRP b2xx series, USB connection
    N3XX = "n3xx"   # USRP n3xx series, Network connection
    X3XX = "x3xx"   # USRP x3xx series, Network connection

class UEBlueCreateModelGeneric(BlueprintNGCreateModel):
    area_id: AreaIDType = Field()
    networks: BlueCreateModelNetworks = Field()
    gnb_host: Optional[IPHostType] = Field(default=None, description="IP of the gNB to connect to, only used when the UE need to connect to a simulated radio")
    usrp: Optional[USRPType] = Field(default=None, description="USRP type to use, only needed in some implementations, if 'rfsim' is used the radio network and gnb_ip is also needed")
    sims: List[UeransimSim] = Field(description="List of SIMs to be used by the UE", min_length=1)

    @model_validator(mode='after')
    def validate_atts(self):
        if self.usrp == USRPType.RFSIM:
            if self.networks.ru1 is None:
                raise ValueError("Radio network (ru1) is needed when using usrp: rfsim")
            if self.gnb_host is None:
                raise ValueError("gNB IP is needed when using usrp: rfsim")
        return self
