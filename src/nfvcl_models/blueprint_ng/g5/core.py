from enum import Enum
from typing import List, Optional

from pydantic import Field

from nfvcl_models.blueprint_ng.core5g.common import SubSubscribers, SubSliceProfiles, SubArea, SubDataNets
from nfvcl_models.blueprint_ng.g5.custom_types_5g import DNNType, SDType, IMSIType
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.custom_types import AreaIDType

class Core5GAttachGNBModel(NFVCLBaseModel):
    area_id: AreaIDType = Field()
    gnb_blue_id: str = Field()

class Core5GAddSubscriberModel(SubSubscribers):
    pass

class Core5GDelSubscriberModel(NFVCLBaseModel):
    imsi: IMSIType = Field()

class Core5GAddSliceModel(SubSliceProfiles):
    area_ids: Optional[List[str]] = Field(default=None)

class Core5GUpdateSliceModel(SubSliceProfiles):
    pass

class Core5GDelSliceModel(NFVCLBaseModel):
    sliceId: SDType = Field()

class Core5GAddTacModel(SubArea):
    pass

class Core5GDelTacModel(NFVCLBaseModel):
    areaId: AreaIDType = Field()

class Core5GAddDnnModel(SubDataNets):
    pass

class Core5GDelDnnModel(NFVCLBaseModel):
    dnn: DNNType = Field()

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
    WEBUI = 'WEBUI'
    METRICFUNC = 'METRICFUNC'

class NetworkFunctionScaling(NFVCLBaseModel):
    nf: NF5GType = Field()
    replica_count: int = Field(gt=-1)
