from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AsyncTaskStatus(str, Enum):
    ready = 'ready'
    deploying = 'deploying'
    processing = 'processing'
    failed = 'failed'
    unknown = 'unknown'


class AsyncTaskResponse(BaseModel):
    status: AsyncTaskStatus = Field(default=AsyncTaskStatus.ready)
    blueprint_id: Optional[str] = Field(default=None)
    detail: str = Field(default="")
    result: dict = Field(default_factory=dict)
    task_id: Optional[str] = Field(default=None)
