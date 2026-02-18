from typing import List, Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.linux.ip import Route
from nfvcl_models.blueprint_ng.g5.common5g import Slice5G


class GNBPDUConfigure(NFVCLBaseModel):
    area: int = Field()

    plmn: str = Field()
    tac: int = Field()
    gnb_id: int = Field()

    amf_ip: str = Field()
    upf_ip: str = Field()
    amf_port: int = Field()

    nssai: List[Slice5G] = Field()

    additional_routes: Optional[List[Route]] = Field(default_factory=list)


class GNBPDUDetach(NFVCLBaseModel):
    area: int = Field()
