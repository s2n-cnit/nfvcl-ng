from __future__ import annotations
from typing import Optional, Literal, List

from pydantic import Field

from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint_ng.core5g.common import SubSliceProfiles, SubDataNets
from nfvcl_core.models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core.models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address


class BlueCreateModelNetworks(NFVCLBaseModel):
    mgt: str = Field()
    n4: str = Field()
    n3: str = Field()
    n6: str = Field()

class UPFNetworkInfo(NFVCLBaseModel):
    n4_cidr: SerializableIPv4Network = Field()
    n3_cidr: SerializableIPv4Network = Field()
    n6_cidr: SerializableIPv4Network = Field()
    n4_ip: SerializableIPv4Address = Field()
    n3_ip: SerializableIPv4Address = Field()
    n6_ip: SerializableIPv4Address = Field()

class UPFBlueCreateModel(BlueprintNGCreateModel):
    area_id: int = Field()
    networks: BlueCreateModelNetworks = Field()
    nrf_ip: Optional[SerializableIPv4Address] = Field(default=None)
    slices: List[SliceModel] = Field(default_factory=list)
    start: Optional[bool] = Field(default=True)
    # Optional because if the UPF is a PDU the routing is fixed
    n3_gateway_ip: Optional[SerializableIPv4Address] = Field(default=None)
    n6_gateway_ip: Optional[SerializableIPv4Address] = Field(default=None)
    gnb_cidr: Optional[SerializableIPv4Network] = Field(default=None)


#####################################################
class DnnModel(NFVCLBaseModel):
    name: Optional[str] = Field(default=None)
    cidr: Optional[str] = Field(default=None)


class SliceModel(NFVCLBaseModel):
    id: str = Field()
    type: Literal["EMBB", "URLLC", "MMTC"] = Field(default="EMBB")
    dnn_list: List[DnnModel] = Field(default_factory=list)

    @classmethod
    def from_slice_profile(cls, slice_profile: SubSliceProfiles, all_dnns: List[SubDataNets]) -> SliceModel:
        dnn_list: List[DnnModel] = []
        for dnn in all_dnns:
            if dnn.dnn in slice_profile.dnnList:
                dnn_list.append(DnnModel(name=dnn.dnn, cidr=dnn.pools[0].cidr))
        return SliceModel(id=slice_profile.sliceId, type=slice_profile.sliceType, dnn_list=dnn_list)

class UpfPayloadModel(NFVCLBaseModel):
    slices: Optional[List[SliceModel]] = Field(default=None)
    nrf_ip: Optional[str] = Field(default=None)
