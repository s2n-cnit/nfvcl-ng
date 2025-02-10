from enum import Enum
from typing import List, Optional

from pydantic import Field

from nfvcl.models.blueprint_ng.core5g.common import NetworkEndPointWithType
from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.blueprints.blueprint import BlueprintNGCreateModel

class RANBlueCreateModelGeneric(BlueprintNGCreateModel):
    mcc: str = Field(alias='mcc', pattern=r'^[0-9]*$', min_length=3, max_length=3)
    mnc: str = Field(alias='mnc', pattern=r'^[0-9]*$', min_length=2, max_length=3)
    sst: str = Field(alias='sst', pattern=r'^[1-3]$', min_length=1, max_length=1)
    sd: str = Field(alias='sd', pattern=r'^([a-fA-F0-9]{6})$')
    tac: str = Field(alias='tac')
    area_id: int = Field(alias='area_id')


################################ CU ###############################################

class CUBlueCreateModelNetwork(NFVCLBaseModel):
    f1: NetworkEndPointWithType = Field(alias='f1')
    n2: NetworkEndPointWithType = Field(alias='n2')
    n3: NetworkEndPointWithType = Field(alias='n3')


class CUBlueCreateModel(RANBlueCreateModelGeneric):
    networks: CUBlueCreateModelNetwork = Field(alias='networks')
    amf: str = Field(alias='amf')

    # @classmethod
    # def create_from_parent(cls, parent: RANBlueCreateModelGeneric, networks, amf):
    #     return CUBlueCreateModel(
    #         mcc=parent.mcc,
    #         mnc=,
    #         sst=,
    #         sd=,
    #         tac=,
    #         area_id=,
    #         networks=,
    #         amf=
    #     )
    #     mcc = parent.mcc,
    #     mnc = self.state.current_config.mnc,
    #     sst = self.state.current_config.sst,
    #     sd = self.state.current_config.sd,
    #     tac = self.state.current_config.tac,
    #     area_id = self.state.current_config.area_id,

################################ CU-CP ############################################

class CUCPBlueCreateModelNetwork(NFVCLBaseModel):
    e1: NetworkEndPointWithType = Field(alias='e1')
    n2: NetworkEndPointWithType = Field(alias='n2')
    f1: NetworkEndPointWithType = Field(alias='f1')


class CUCPBlueCreateModel(RANBlueCreateModelGeneric):
    networks: CUCPBlueCreateModelNetwork = Field(alias='networks')
    amf: str = Field(alias='amf')


################################ CU-UP ############################################

class CUUPBlueCreateModelNetwork(NFVCLBaseModel):
    e1: NetworkEndPointWithType = Field(alias='e1')
    n3: NetworkEndPointWithType = Field(alias='n3')
    f1: NetworkEndPointWithType = Field(alias='f1')


class CUUPBlueCreateModel(RANBlueCreateModelGeneric):
    networks: CUUPBlueCreateModelNetwork = Field(alias='networks')


################################ DU ############################################

class DUBlueCreateModelNetwork(NFVCLBaseModel):
    f1: NetworkEndPointWithType = Field(alias='f1')
    ru1: NetworkEndPointWithType = Field(alias='ru1')
    ru2: NetworkEndPointWithType = Field(alias='ru2')


class DUBlueCreateModel(RANBlueCreateModelGeneric):
    networks: DUBlueCreateModelNetwork = Field(alias='networks')
    usrp: str = Field(alias='usrp')


################################ GNB ############################################

class GNBBlueCreateModelNetwork(NFVCLBaseModel):
    n2: NetworkEndPointWithType = Field(alias='n2')
    n3: NetworkEndPointWithType = Field(alias='n3')
    ru1: NetworkEndPointWithType = Field(alias='ru1')
    ru2: NetworkEndPointWithType = Field(alias='ru2')


class GNBBlueCreateModel(RANBlueCreateModelGeneric):
    networks: Optional[GNBBlueCreateModelNetwork] = Field(default=None, alias='networks')
    usrp: str = Field(alias='usrp')
    amf: Optional[str] = Field(default='oai-amf', alias='amf')


################################ RAN ############################################
class Split(str, Enum):
    GNB = '1'
    CU_DU = '2'
    CP_UP_DU = '3'


class RANBlueCreateModelNetwork(NFVCLBaseModel):
    f1: Optional[NetworkEndPointWithType] = Field(default=None, alias='f1')
    e1: Optional[NetworkEndPointWithType] = Field(default=None, alias='e1')
    n2: Optional[NetworkEndPointWithType] = Field(default=None, alias='n2')
    n3: Optional[NetworkEndPointWithType] = Field(default=None, alias='n3')
    ru1: Optional[NetworkEndPointWithType] = Field(default=None, alias='ru1')
    ru2: Optional[NetworkEndPointWithType] = Field(default=None, alias='ru2')


class RANBlueCreateModelSplit(NFVCLBaseModel):
    cu: bool = Field(default=False, alias='cu')
    cu_cp: bool = Field(default=False, alias='cu-cp')
    cu_up: bool = Field(default=False, alias='cu-up')
    du: bool = Field(default=False, alias='du')
    gnb: bool = Field(default=True, alias='gnb')


class RANBlueCreateModel(RANBlueCreateModelGeneric):
    split: Split = Field(default=Split.GNB, alias='split')
    networks: RANBlueCreateModelNetwork = Field(alias='networks')
    ran: RANBlueCreateModelSplit = Field(alias='ran')
    cuCpHost: str = Field(alias='cucpHost')
    amf: str = Field(alias='amf')
    usrp: str = Field(alias='usrp')
