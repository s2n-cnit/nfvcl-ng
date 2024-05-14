from typing import List, Optional

from pydantic import Field

from blueprints.blue_5g_base.models.blue_5g_model import SubSubscribers, SubSliceProfiles, SubArea, SubDataNets
from models.base_model import NFVCLBaseModel


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


class Core5GDelTacModel(SubArea):
    pass


class Core5GAddDnnModel(SubDataNets):
    pass


class Core5GDelDnnModel(NFVCLBaseModel):
    dnn: str = Field()
