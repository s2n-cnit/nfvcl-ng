from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict

from pydantic import Field

from nfvcl.models.base_model import NFVCLBaseModel

class BlueprintPerformanceType(str, Enum):
    DAY0 = 'day0'
    DAY2 = 'day2'
    DELETION = 'deletion'

class BlueprintPerformanceProviderCall(NFVCLBaseModel):
    id: str = Field()
    method_name: str = Field()
    info: Dict[str, str] = Field(default_factory=dict)
    start: datetime = Field()
    end: Optional[datetime] = Field(default=None)
    duration: Optional[int] = Field(default=None)

class BlueprintPerformanceOperation(NFVCLBaseModel):
    id: str = Field()
    op_name: str = Field()
    type: BlueprintPerformanceType
    start: datetime = Field()
    end: Optional[datetime] = Field(default=None)
    duration: Optional[int] = Field(default=None)
    provider_calls: List[BlueprintPerformanceProviderCall] = Field(default_factory=list)

class BlueprintPerformance(NFVCLBaseModel):
    blueprint_id: str = Field()
    blueprint_type: str = Field()
    start: datetime = Field()
    operations: List[BlueprintPerformanceOperation] = Field(default_factory=list)
