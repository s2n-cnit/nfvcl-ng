from typing import List, Any

from pydantic import Field, field_validator

from nfvcl_core_models.custom_types import AreaIDType
from nfvcl_models.blueprint_ng.core5g.common import NetworkEndPoint, NetworkEndPointWithType
from nfvcl_models.blueprint_ng.g5.ue import UESim
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel


class PacketRusherNetworkEndpoints(NFVCLBaseModel):
    mgt: NetworkEndPoint = Field(description='Name of the network to be used for management')
    n2: NetworkEndPointWithType = Field(description='Name of the network to be used for the N2 control plane connection to the AMF')
    n3: NetworkEndPointWithType = Field(description='Name of the network to be used for the N3 data plane connection to the UPF')

    @field_validator("mgt", mode="before")
    def str_to_network_endpoint(cls, v: object) -> object:
        if isinstance(v, str):
            return NetworkEndPoint(net_name=v)
        return v

    @field_validator("n2", "n3", mode="before")
    def str_to_network_endpoint_with_type(cls, v: object) -> object:
        if v and isinstance(v, str):
            return NetworkEndPointWithType(net_name=v)
        return v


class PacketRusherConfig(NFVCLBaseModel):
    network_endpoints: PacketRusherNetworkEndpoints


class PacketRusherArea(NFVCLBaseModel):
    id: AreaIDType = Field(..., description='Area identifier, used as TAC in the gNB configuration')
    sims: List[UESim] = Field(default_factory=list, description='List of SIMs to be configured on the PacketRusher VM')

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, PacketRusherArea):
            return other.id == self.id
        return False


class PacketRusherBlueprintRequestInstance(BlueprintNGCreateModel):
    config: PacketRusherConfig
    areas: List[PacketRusherArea] = Field(..., description='List of areas to instantiate the Blueprint', min_length=1)

    class Config:
        use_enum_values = True


class PacketRusherBlueprintRequestAddDelArea(NFVCLBaseModel):
    area_id: str = Field()


class PacketRusherBlueprintRequestAddSim(NFVCLBaseModel):
    area_id: str = Field()
    sim: UESim = Field()


class PacketRusherBlueprintRequestDelSim(NFVCLBaseModel):
    area_id: str = Field()
    imsi: str = Field()
