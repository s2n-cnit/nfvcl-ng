

from typing import Optional, List

from pydantic import Field

from nfvcl_models.blueprint_ng.core5g.common import SubSliceProfiles, SubDataNets, NetworkEndPoint, NetworkEndPointWithType, Router5GNetworkInfo
from nfvcl_models.blueprint_ng.g5.common5g import Slice5G
from nfvcl_models.blueprint_ng.g5.custom_types_5g import DNNType
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core_models.custom_types import AreaIDType
from nfvcl_core_models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address


class BlueCreateModelNetworks(NFVCLBaseModel):
    mgt: NetworkEndPoint = Field()
    n4: NetworkEndPointWithType = Field()
    n3: NetworkEndPointWithType = Field()
    n6: NetworkEndPointWithType = Field()
    gnb: Optional[NetworkEndPointWithType] = Field(default=None)

class UPFNetworkInfo(NFVCLBaseModel):
    n4_cidr: SerializableIPv4Network = Field()
    n3_cidr: SerializableIPv4Network = Field()
    n6_cidr: SerializableIPv4Network = Field()
    n4_ip: SerializableIPv4Address = Field()
    n3_ip: SerializableIPv4Address = Field()
    n6_ip: SerializableIPv4Address = Field()

class UPFBlueCreateModel(BlueprintNGCreateModel):
    area_id: AreaIDType = Field()
    networks: BlueCreateModelNetworks = Field()
    nrf_ip: Optional[SerializableIPv4Address] = Field(default=None)
    smf_ip: Optional[SerializableIPv4Address] = Field(default=None)
    slices: List[Slice5GWithDNNs] = Field(default_factory=list)
    start: Optional[bool] = Field(default=True)
    # Optional because if the UPF is a PDU the routing is fixed
    n3_gateway_ip: Optional[SerializableIPv4Address] = Field(default=None)
    n6_gateway_ip: Optional[SerializableIPv4Address] = Field(default=None)
    gnb_cidr: Optional[SerializableIPv4Network] = Field(default=None)
    external_router: Optional[Router5GNetworkInfo] = Field(default=None)


#####################################################
class DnnWithCidrModel(NFVCLBaseModel):
    dnn: Optional[DNNType] = Field(default=None)
    cidr: Optional[str] = Field(default=None)

class Slice5GWithDNNs(Slice5G):
    dnn_list: List[DnnWithCidrModel] = Field(default_factory=list)

    @classmethod
    def from_slice_profile(cls, slice_profile: SubSliceProfiles, all_dnns: List[SubDataNets]) -> Slice5GWithDNNs:
        dnn_list: List[DnnWithCidrModel] = []
        for dnn in all_dnns:
            if dnn.dnn in slice_profile.dnnList:
                dnn_list.append(DnnWithCidrModel(dnn=dnn.dnn, cidr=dnn.pools[0].cidr))
        return Slice5GWithDNNs(sd=slice_profile.sliceId, sst=slice_profile.sliceType, dnn_list=dnn_list)

class UpfPayloadModel(NFVCLBaseModel):
    slices: Optional[List[Slice5GWithDNNs]] = Field(default=None)
    nrf_ip: Optional[str] = Field(default=None)
