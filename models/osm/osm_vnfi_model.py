from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel, Field

class OSM(BaseModel):
    count_index: int
    member_vnf_index: str
    ns_id: str
    vdu: dict
    vdu_id: str
    vim_account_id: str
    vnf_id: str
    vnfd_id: str
    vnfd_ref: str


class AdditionalParams(BaseModel):
    OSM: OSM

class InterfaceOSM(BaseModel):
    external_connection_point_ref: str = Field(
        ..., alias='external-connection-point-ref'
    )
    internal_connection_point_ref: str = Field(
        ..., alias='internal-connection-point-ref'
    )
    mgmt_interface: Optional[bool] = Field(None, alias='mgmt-interface')
    mgmt_vnf: Optional[bool] = Field(None, alias='mgmt-vnf')
    name: str
    ns_vld_id: str = Field(..., alias='ns-vld-id')
    type: str
    port_security: bool
    compute_node: str
    ip_address: str = Field(..., alias='ip-address')
    mac_address: str = Field(..., alias='mac-address')
    pci: Any
    vlan: Optional[int]


class InternalConnectionPointItem(BaseModel):
    connection_point_id: str = Field(..., alias='connection-point-id')
    id: str
    name: str

class VirtualStorage(BaseModel):
    id: str
    size_of_storage: str = Field(..., alias='size-of-storage')


class VdurItem(BaseModel):
    _id: str
    additionalParams: AdditionalParams
    affinity_or_anti_affinity_group_id: List = Field(
        ..., alias='affinity-or-anti-affinity-group-id'
    )
    cloud_init: str = Field(..., alias='cloud-init')
    count_index: int = Field(..., alias='count-index')
    id: str
    interfaces: List[InterfaceOSM]
    internal_connection_point: List[InternalConnectionPointItem] = Field(
        ..., alias='internal-connection-point'
    )
    ip_address: str = Field(..., alias='ip-address')
    ns_flavor_id: str = Field(..., alias='ns-flavor-id')
    ns_image_id: str = Field(..., alias='ns-image-id')
    vdu_id_ref: str = Field(..., alias='vdu-id-ref')
    vdu_name: str = Field(..., alias='vdu-name')
    vim_info: dict
    virtual_storages: List[VirtualStorage] = Field(..., alias='virtual-storages')
    status: str
    vim_id: str = Field(..., alias='vim-id')
    name: str

class ConnectionPointItem(BaseModel):
    name: str
    connection_point_id: str = Field(..., alias='connection-point-id')
    connection_point_vdu_id: str = Field(..., alias='connection-point-vdu-id')
    id: str


class VNFiModelOSM(BaseModel):
    _id: str
    id: str
    nsr_id_ref: str = Field(..., alias='nsr-id-ref')
    member_vnf_index_ref: str = Field(..., alias='member-vnf-index-ref')
    additionalParamsForVnf: Any
    created_time: float = Field(..., alias='created-time')
    vnfd_ref: str = Field(..., alias='vnfd-ref')
    vnfd_id: str = Field(..., alias='vnfd-id')
    vim_account_id: str = Field(..., alias='vim-account-id')
    vca_id: Any = Field(..., alias='vca-id')
    vdur: List[VdurItem]
    connection_point: List[ConnectionPointItem] = Field(..., alias='connection-point')
    ip_address: str = Field(..., alias='ip-address')
    revision: int


class VNFiModelListOSM(BaseModel):
    vnf_list: List[VNFiModelOSM] = []
