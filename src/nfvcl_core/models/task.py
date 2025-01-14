from typing import Callable, Any, Optional


class NFVCLTask:
    def __init__(self, callable_function: Callable, callback_function: Optional[Callable], *args, **kwargs):
        self.callable_function = callable_function
        self.args = args
        self.kwargs = kwargs
        self.callback_function = callback_function

class NFVCLTaskResult:
    def __init__(self, result: Any, error = False, exception: Exception = None):
        self.result = result
        self.error = error
        self.exception = exception

    def __str__(self):
        return f"Result: {self.result}, Error: {self.error}, Exception: {self.exception}"
