from typing import List, Optional

from nfvcl.models.linux.ip import Route
from pydantic import Field

from nfvcl.models.base_model import NFVCLBaseModel


class GNBPDUSlice(NFVCLBaseModel):
    sst: int = Field()
    sd: int = Field()

class GNBPDUConfigure(NFVCLBaseModel):
    area: int = Field()

    plmn: str = Field()
    tac: int = Field()

    amf_ip: str = Field()
    amf_port: int = Field()

    nssai: List[GNBPDUSlice] = Field()

    additional_routes: Optional[List[Route]] = Field(default_factory=list)
