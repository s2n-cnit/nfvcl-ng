from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any

from pydantic import BaseModel, Field

from models.base_model import NFVCLBaseModel
from models.network import PduInterface
from models.prometheus.prometheus_model import PrometheusTargetModel
from models.vim.vim_models import VimLink, VimNetMap


class BlueVNFD(NFVCLBaseModel):
    id: str
    name: str
    vl: Optional[List[VimLink]] | Optional[List[VimNetMap]] | Optional[List[PduInterface]] = Field(default=None)
    area_id: int = Field(default=-1)
    type: str = Field(default="")


class BlueVNFDs(NFVCLBaseModel):
    core: List[BlueVNFD] = Field(default=[])
    area: List[BlueVNFD] = Field(default=[])
    ues: List[BlueVNFD] = Field(default=[])


class BlueVLD(NFVCLBaseModel):
    name: str
    vim_network_name: str = Field(alias="vim-network-name")


class BlueKDUConf(NFVCLBaseModel):
    kdu_name: str = Field(default="")
    k8s_namespace: Optional[str] = Field(default=None, alias="k8s-namespace")
    additionalParams: Dict[str, Any] = Field(default={})


class BlueVNFAdditionalParams(NFVCLBaseModel):
    member_vnf_index: str = Field(default="", alias="member-vnf-index")
    additionalParamsForKdu: Optional[List[BlueKDUConf]] = Field(default=None)


class BlueDeployConfig(NFVCLBaseModel):
    vld: List[BlueVLD] = Field(default=[])
    additionalParamsForVnf: List[BlueVNFAdditionalParams] = Field(default=[])
    nsdId: str = Field(default="")
    nsName: str = Field(default="")
    nsDescription: str = Field(default="")
    vimAccountId: str = Field(default="")


class BlueDescrVLD(NFVCLBaseModel):
    id: str
    mgmt_network: bool = Field(alias="mgmt-network")


class ConstituentCpdId(NFVCLBaseModel):
    constituent_cpd_id: str = Field(alias="constituent-cpd-id")
    constituent_base_element_id: str = Field(alias="constituent-base-element-id")


class VirtualLinkConnect(NFVCLBaseModel):
    constituent_cpd_id: List[ConstituentCpdId] = Field(alias="constituent-cpd-id")
    virtual_link_profile_id: str = Field(alias="virtual-link-profile-id")


class BlueVNFProfile(NFVCLBaseModel):
    id: str
    vnfd_id: str = Field(alias="vnfd-id")
    virtual_link_connectivity: List[VirtualLinkConnect] = Field(alias="virtual-link-connectivity")


class BlueDF(NFVCLBaseModel):
    id: str
    vnf_profile: List[BlueVNFProfile] = Field(alias="vnf-profile")


class BlueDescrNsdItem(NFVCLBaseModel):
    name: str
    id: str
    description: str
    df: List[BlueDF]
    virtual_link_descriptor: List[BlueDescrVLD] = Field(alias="virtual-link-desc")
    version: str
    vnfd_id: List[str] = Field(alias="vnfd-id")


class BlueDescrNsd(NFVCLBaseModel):
    nsd: List[BlueDescrNsdItem]


class BlueDescr(NFVCLBaseModel):
    nsd: BlueDescrNsd


class BlueNSD(NFVCLBaseModel):
    status: str
    vim: str
    type: str
    descr: BlueDescr
    deploy_config: BlueDeployConfig
    nsd_id: str = Field(default="")
    nsi_id: str = Field(default="")
    area_id: int = Field(default=-1)
    replica_id: int = Field(default=-1)  # Needed in K8S, is it really necessary?
    ue_id: Optional[str] = Field(default=None, description="Used by ueransim blue to save the UE id")
    vld: List[PduInterface] = Field(default=[])


class BlueprintVersion(str, Enum):
    ver1_00: str = '1.00'
    ver2_00: str = '2.00'


class BlueprintBaseModel(NFVCLBaseModel):
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
    node_exporters: List[PrometheusTargetModel] = Field(default=[], description="List of node exporters (for prometheus) active in the blueprint.")
    prometheus_scraper_id: Optional[str] = Field(default=None, description="The prometheus instance in charge of metric scraping")

    """
    @field_validator('timestamp')
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
