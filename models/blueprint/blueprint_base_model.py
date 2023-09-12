from datetime import datetime
from enum import Enum
from typing import List, Dict
from pydantic import BaseModel, Field


class BlueVNFD(BaseModel):
    id: str
    name: str
    v1: str = Field(default="")
    area_id: int = Field(default=-1)
    type: str = Field(default="")


class BlueVNFDs(BaseModel):
    core: List[BlueVNFD] = Field(default=[])
    area: List[BlueVNFD] = Field(default=[])


class BlueVLD(BaseModel):
    name: str
    vim_network_name: str = Field(alias="vim-network-name")  # = Field(alias="vim-network-name")


class BLueDeployConfig(BaseModel):
    vld: List[BlueVLD] = Field(default=[])
    nsdId: str = Field(default="")
    nsName: str = Field(default="")
    nsDescription: str = Field(default="")
    vimAccountId: str = Field(default="")


class BlueDescrVLD(BaseModel):
    id: str
    mgmt_network: bool = Field(alias="mgmt-network")


class ConstituentCpdId(BaseModel):
    constituent_cpd_id: str = Field(alias="constituent-cpd-id")
    constituent_base_element_id: str = Field(alias="constituent-base-element-id")


class VirtualLinkConnect(BaseModel):
    constituent_cpd_id: List[ConstituentCpdId] = Field(alias="constituent-cpd-id")
    virtual_link_profile_id: str = Field(alias="virtual-link-profile-id")


class BlueVNFProfile(BaseModel):
    id: str
    vnfd_id: str = Field(alias="vnfd-id")
    virtual_link_connectivity: List[VirtualLinkConnect] = Field(alias="virtual-link-connectivity")


class BlueDF(BaseModel):
    id: str
    vnf_profile: List[BlueVNFProfile] = Field(alias="vnf-profile")


class BlueDescrNsdItem(BaseModel):
    name: str
    id: str
    description: str
    df: List[BlueDF]
    virtual_link_descriptor: List[BlueDescrVLD] = Field(alias="virtual-link-desc")
    version: str
    vnfd_id: List[str] = Field(alias="vnfd-id")


class BlueDescrNsd(BaseModel):
    nsd: List[BlueDescrNsdItem]


class BlueDescr(BaseModel):
    nsd: BlueDescrNsd


class BlueNSD(BaseModel):
    status: str
    vim: str
    type: str
    descr: BlueDescr
    deploy_config: BLueDeployConfig
    nsd_id: str = Field(default="")
    nsi_id: str = Field(default="")
    area_id: int = Field(default=-1)  # Needed in VyOS, is it really necessary?
    replica_id: int = Field(default=-1)  # Needed in K8S, is it really necessary?


class BlueprintVersion(str, Enum):
    ver1_00: str = '1.00'
    ver2_00: str = '2.00'


class BlueprintBaseModel(BaseModel):
    id: str
    version: BlueprintVersion = Field(default=BlueprintVersion.ver1_00.value)
    conf: dict
    # conf["blueprint_instance_id"] = id_
    input_conf: dict = Field(description="Configuration received on blueprint creation")
    nsd_: List[BlueNSD] = Field(default=[])
    vnfd: BlueVNFDs = Field(default=BlueVNFDs())
    pdu: List = Field(default=[])
    vnf_configurator: List = Field(default=[])
    primitives: List[dict] = Field(default=[])
    action_to_check: List = Field(default=[])
    config_len: dict = Field(default={})
    timestamp: Dict[str, datetime] = Field(default={})
    created: datetime = Field(default=datetime.now())
    modified: datetime = Field(default=datetime.now())
    status: str = Field(default='idle')
    detailed_status: str = Field(default="")
    current_operation: str = Field(default="")
    supported_operations: dict = Field(default={})
    type: str
    vnfi: List = Field(default=[])
    deployment_units: List = Field(default=[])
    node_exporters: List = Field(default=[], description="List of node exporters active in the blueprint.")

    """
    @validator('timestamp')
    def standardize_cid(cls, timestamp: dict):
       
        if timestamp is not None:
            for key in timestamp.keys():
                if not isinstance(timestamp[key], datetime):
                    try:
                        timestamp[key] = datetime.fromisoformat(timestamp[key])
                    except (TypeError, ValueError) as e:
                        timestamp[key] = datetime.now()
        return timestamp
    """

