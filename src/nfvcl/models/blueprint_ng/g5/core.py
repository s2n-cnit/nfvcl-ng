from enum import Enum
from typing import List, Optional

from pydantic import Field

from nfvcl.models.blueprint_ng.core5g.common import SubSubscribers, SubSliceProfiles, SubArea, SubDataNets
from nfvcl.models.base_model import NFVCLBaseModel


class Core5GAttachGNBModel(NFVCLBaseModel):
    area_id: int = Field()
    gnb_blue_id: str = Field()


class Core5GAddSubscriberModel(SubSubscribers):
    pass


class Core5GDelSubscriberModel(NFVCLBaseModel):
    imsi: str = Field()


class Core5GAddSliceModel(SubSliceProfiles):
    area_ids: Optional[List[str]] = Field(default=None)


class Core5GUpdateSliceModel(SubSliceProfiles):
    pass


class Core5GDelSliceModel(NFVCLBaseModel):
    sliceId: str = Field()


class Core5GAddTacModel(SubArea):
    pass

class Core5GDelTacModel(NFVCLBaseModel):
    areaId: int = Field()


class Core5GAddDnnModel(SubDataNets):
    pass


class Core5GDelDnnModel(NFVCLBaseModel):
    dnn: str = Field()

class NF5GType(str, Enum):
    AMF = 'AMF'
    SMF = 'SMF'
    NSSF = 'NSSF'
    NEF = 'NEF'
    NRF = 'NRF'
    PCF = 'PCF'
    UDM = 'UDM'
    UDR = 'UDR'
    AF = 'AF'
    AUSF = 'AUSF'

class NetworkFunctionScaling(NFVCLBaseModel):
    nf: NF5GType = Field()
    replica_count: int = Field()
