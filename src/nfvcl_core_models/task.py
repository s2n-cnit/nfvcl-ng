import uuid
from enum import Enum
from typing import Callable, Any, Optional

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel


class NFVCLTask:
    def __init__(self, callable_function: Callable, callback_function: Optional[Callable], *args, **kwargs):
        self.task_id = str(uuid.uuid4())
        self.callable_function = callable_function
        self.args = args
        self.kwargs = kwargs
        self.callback_function = callback_function

class NFVCLTaskResult:
    def __init__(self, task_id: str, result: Any, error = False, exception: Exception = None):
        self.task_id = task_id
        self.result = result
        self.error = error
        self.exception = exception

    def __str__(self):
        return f"Result: {self.result}, Error: {self.error}, Exception: {self.exception}"

class NFVCLTaskStatusType(str, Enum):
    RUNNING = "running"
    DONE = "done"

class NFVCLTaskStatus(NFVCLBaseModel):
    task_id: str = Field()
    status: NFVCLTaskStatusType = Field()
    result: Optional[str] = Field(default=None)
    error: bool = Field(default=False)
    exception: Optional[str] = Field(default=None)
