from pydantic import BaseModel
from typing import List, Optional, Union, Dict
import datetime
# from enum import Enum
# from ipaddress import IPv4Network, IPv4Address


class NetworkServiceSummaryModel(BaseModel):
    status: str
    type: str
    vim: str
    nsi_id: str
    nsd_id: str
    area: Optional[int]
    descr: dict
    deploy_config: dict


class VnfDescriptorReference(BaseModel):
    id: Optional[str]
    name: Optional[str]
    v1: Optional[dict]
    area_id: Optional[int]
    type: Optional[str]


class ShortBlueModel(BaseModel):
    id: str
    type: str
    status: str
    detailed_status: Union[str, None]
    current_operation: Union[str, None]
    created: datetime.datetime
    modified: Optional[datetime.datetime] = None
    no_areas: int
    no_nsd: int
    no_primitives: int


class DetailedBlueModel(BaseModel):
    id: str
    type: str
    status: str
    detailed_status: Union[str, None] = None
    current_operation: Union[str, None] = None
    created: datetime.datetime
    modified: Optional[datetime.datetime] = None
    supported_ops: Dict[str, List] = None
    areas: List[dict] = []
    ns: List[NetworkServiceSummaryModel] = []
    vnfd: Dict[str, List[VnfDescriptorReference]] = None
    primitives: Optional[List[dict]]
