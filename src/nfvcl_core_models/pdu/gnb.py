from typing import List, Optional

from nfvcl_models.blueprint_ng.g5.common5g import Slice5G
from nfvcl_core_models.linux.ip import Route
from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel

class GNBPDUConfigure(NFVCLBaseModel):
    area: int = Field()

    plmn: str = Field()
    tac: int = Field()

    amf_ip: str = Field()
    upf_ip: str = Field()
    amf_port: int = Field()

    nssai: List[Slice5G] = Field()

    additional_routes: Optional[List[Route]] = Field(default_factory=list)
