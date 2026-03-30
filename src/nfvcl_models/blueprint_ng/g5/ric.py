from typing import Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.custom_types import AreaIDType
from nfvcl_core_models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPoint, NetworkEndPointWithType

class RICNetworkInfo(NFVCLBaseModel):
    e2_ip: SerializableIPv4Address = Field()
    mgt_ip: SerializableIPv4Address = Field()

class RICBlueCreateModel(NFVCLBaseModel):
    area_id: AreaIDType = Field(alias='areaId')
    mgt: NetworkEndPoint = Field()
    e2: NetworkEndPointWithType = Field()
    port: int = Field()
    gnb_pdu_name: str = Field(alias='gnbPduName')

class RICRunXappModel(NFVCLBaseModel):
    xapp_name: str = Field(alias='xappName')
    command: str = Field()

class RICOnboardXappModel(NFVCLBaseModel):
    xapp_name: str = Field(alias='xappName')
    xapp_url: str = Field(alias='xappUrl')

class RicDeleteXappModel(NFVCLBaseModel):
    xapp_name: str = Field(alias='xappName')
