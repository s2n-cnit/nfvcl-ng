from pydantic import BaseModel, Field


class VirtLinkDescr(BaseModel):
    nsd_id: str = Field(default="")
    ns_vld_id: str
    vnfi_id: str
    vnfd_name: str = Field(default="")
    ip: str = Field(default="")
    intf_name: str = Field(default="")
    external_cp_ref: str = Field(default="", alias="external-cp-ref")
    member_vnf_index_ref: str = Field(default="", alias="member-vnf-index-ref")
    intf_mac: str = Field(default="")
    compute_node: str = Field(default="")
