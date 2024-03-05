from enum import Enum
from typing import Any
from models.base_model import NFVCLBaseModel


class WorkerMessageType(Enum):
    """
    Indicates the type of message to the worker process.
    """
    DAY0 = 'DAY0'
    DAY2 = 'DAY2'
    STOP = 'STOP'


class WorkerMessage(NFVCLBaseModel):
    """
    Used by the main process to send requests to the worker process.
    """
    message_type: WorkerMessageType
    path: str # The request path
    message: Any # The message content
