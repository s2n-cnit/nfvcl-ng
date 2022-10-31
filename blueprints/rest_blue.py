from pydantic import BaseModel
from typing import List, Optional, Union
import datetime
# from enum import Enum
# from ipaddress import IPv4Network, IPv4Address


class NetworkServiceSummaryModel(BaseModel):
    status: str
    type: str
    vim: dict
    nsi_id: str
    nsd_id: str


class VnfDescriptorReference(BaseModel):
    id: str
    name: str


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
    supported_ops: List[str] = []
    areas: List[dict] = []
    ns: List[NetworkServiceSummaryModel] = []
    vnfd: List[VnfDescriptorReference] = []
    primitives: Optional[List[dict]]
