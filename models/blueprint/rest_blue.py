from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict
import datetime


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
    detailed_status: str = Field(default="", description="Detailed description of the blueprint status")
    current_operation: str = Field(default="")
    created: datetime.datetime = Field(default=datetime.datetime.now())
    modified: Optional[datetime.datetime]
    no_areas: int = Field(default=-1, description="Number of areas. -1 when not initialized")
    no_nsd: int = Field(default=-1, description="Number of nsd. -1 when not initialized")
    no_primitives: int = Field(default=-1, description="Number of primitives. -1 when not initialized")


class DetailedBlueModel(BaseModel):
    id: str
    type: str
    status: str
    detailed_status: str = Field(default="", description="Detailed description of the blueprint status")
    current_operation: str = Field(default="")
    created: datetime.datetime = Field(default=datetime.datetime.now())
    modified: Optional[datetime.datetime] = None
    supported_operations: Dict[str, List] = None
    areas: List[dict] = []
    nsd_: List[NetworkServiceSummaryModel] = []
    vnfd: Dict[str, List[VnfDescriptorReference]] = None
    primitives: List[dict] = Field(default=[])


class BlueGetDataModel(BaseModel):
    blue_id: str = Field(description="The ID of the blueprint from witch the data is retrieved")
    type: str = Field(description="The type of data to obtain")
    arguments: dict = Field(description="Parameters required from the type of request")

