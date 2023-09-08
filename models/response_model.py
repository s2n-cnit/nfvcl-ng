from enum import Enum

from pydantic import BaseModel, Field

class OssStatus(str, Enum):
    ready: str = 'ready'
    failed: str = 'failed'
    unknown: str = 'unknown'


class OssCompliantResponse(BaseModel):
    status: OssStatus = Field(default=OssStatus.ready)
    detail: str = Field(default="")
    result: dict = Field(default={})


