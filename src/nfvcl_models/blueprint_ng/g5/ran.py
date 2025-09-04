from enum import Enum
from typing import Optional, List

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core_models.custom_types import AreaIDType
from nfvcl_core_models.linux.ip import Route
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPointWithType
from nfvcl_models.blueprint_ng.g5.common5g import Slice5G


class RanInterfacesIps(NFVCLBaseModel):
    n2: Optional[str] = Field(default=None)
    n3: Optional[str] = Field(default=None)
    f1_cu: Optional[str] = Field(default=None, alias="f1Cu")
    f1_du: Optional[str] = Field(default=None, alias="f1Du")
    f1_cu_cp: Optional[str] = Field(default=None, alias="f1CuCp")
    f1_cu_up: Optional[str] = Field(default=None, alias="f1CuUp")
    e1_cu_cp: Optional[str] = Field(default=None, alias="e1CuCp")
    e1_cu_up: Optional[str] = Field(default=None, alias="e1CuUp")
    ru1: Optional[str] = Field(default=None)
    ru2: Optional[str] = Field(default=None)

class RANBlueCreateModelGeneric(BlueprintNGCreateModel):
    mcc: str = Field(alias='mcc', pattern=r'^[0-9]*$', min_length=3, max_length=3)
    mnc: str = Field(alias='mnc', pattern=r'^[0-9]*$', min_length=2, max_length=3)
    snssai_list: List[Slice5G] = Field(alias='snssaiList')
    tac: int = Field(alias='tac')
    area_id: AreaIDType = Field(alias='area_id')
    gnb_id: Optional[int] = Field(default=1, alias='gnb_id')
    additional_routes: Optional[List[Route]] = Field(default_factory=list, alias='additional_routes')


################################ CU ###############################################

class CUBlueCreateModelNetwork(NFVCLBaseModel):
    f1: NetworkEndPointWithType = Field(alias='f1')
    n2: NetworkEndPointWithType = Field(alias='n2')
    n3: NetworkEndPointWithType = Field(alias='n3')


class CUBlueCreateModel(RANBlueCreateModelGeneric):
    networks: CUBlueCreateModelNetwork = Field(alias='networks')
    amf: Optional[str] = Field(default='127.0.0.1', alias='amf')


################################ CU-CP ############################################

class CUCPBlueCreateModelNetwork(NFVCLBaseModel):
    e1: NetworkEndPointWithType = Field(alias='e1')
    n2: NetworkEndPointWithType = Field(alias='n2')
    f1: NetworkEndPointWithType = Field(alias='f1')


class CUCPBlueCreateModel(RANBlueCreateModelGeneric):
    networks: CUCPBlueCreateModelNetwork = Field(alias='networks')
    amf: Optional[str] = Field(default='127.0.0.1', alias='amf')
    f1_port: Optional[str] = Field(default="2153", alias='f1Port')


################################ CU-UP ############################################

class CUUPBlueCreateModelNetwork(NFVCLBaseModel):
    e1: NetworkEndPointWithType = Field(alias='e1')
    n3: NetworkEndPointWithType = Field(alias='n3')
    f1: NetworkEndPointWithType = Field(alias='f1')


class CUUPBlueCreateModel(RANBlueCreateModelGeneric):
    networks: CUUPBlueCreateModelNetwork = Field(alias='networks')
    cucp_host: Optional[str] = Field(alias='cuCpHost')


################################ DU ############################################

class DUBlueCreateModelNetwork(NFVCLBaseModel):
    f1: NetworkEndPointWithType = Field(alias='f1')
    ru1: NetworkEndPointWithType = Field(alias='ru1')
    ru2: NetworkEndPointWithType = Field(alias='ru2')


class DUBlueCreateModel(RANBlueCreateModelGeneric):
    networks: DUBlueCreateModelNetwork = Field(alias='networks')
    usrp: str = Field(alias='usrp')
    f1_port: Optional[str] = Field(default="2153", alias='f1Port')
    cu_host: Optional[str] = Field(default="cu", alias='cuHost')


################################ GNB ############################################

class GNBBlueCreateModelNetwork(NFVCLBaseModel):
    n2: NetworkEndPointWithType = Field(alias='n2')
    n3: NetworkEndPointWithType = Field(alias='n3')
    ru1: NetworkEndPointWithType = Field(alias='ru1')
    ru2: NetworkEndPointWithType = Field(alias='ru2')


class GNBBlueCreateModel(RANBlueCreateModelGeneric):
    networks: Optional[GNBBlueCreateModelNetwork] = Field(default=None, alias='networks')
    usrp: str = Field(alias='usrp')
    amf: Optional[str] = Field(default='127.0.0.1', alias='amf')


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


class RANBlueCreateModel(RANBlueCreateModelGeneric):
    split: Split = Field(default=Split.GNB, alias='split')
    networks: RANBlueCreateModelNetwork = Field(alias='networks')
    amf_host: Optional[str] = Field(default="127.0.0.1", alias='amfHost')
    cu_host: Optional[str] = Field(default="cu", alias='cuHost')
    cucp_host: Optional[str] = Field(default="cucp", alias='cucpHost')
    usrp: str = Field(alias='usrp')
