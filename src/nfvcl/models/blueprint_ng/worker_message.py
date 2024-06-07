from enum import Enum
from typing import Any, Optional, Callable

from pydantic import Field

from nfvcl.models.base_model import NFVCLBaseModel


class WorkerMessageType(Enum):
    """
    Indicates the type of message to the worker process.
    """
    DAY0 = 'DAY0'
    DAY2 = 'DAY2'
    DAY2_BY_NAME = 'DAY2_BY_NAME'
    STOP = 'STOP'


class WorkerMessage(NFVCLBaseModel):
    """
    Used by the main process to send requests to the worker process.
    """
    message_type: WorkerMessageType
    path: str # The request path
    message: Any # The message content
    callback: Optional[Callable[[Any], Any]] = Field(default=None)
