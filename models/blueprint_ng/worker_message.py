from enum import Enum
from typing import Any
from models.base_model import NFVCLBaseModel


class WorkerMessageType(Enum):
    DAY0 = 'DAY0'
    DAY2 = 'DAY2'
    STOP = 'STOP'


class WorkerMessage(NFVCLBaseModel):
    message_type: WorkerMessageType
    path: str
    message: Any
