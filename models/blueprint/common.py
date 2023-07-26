from typing import Literal

from pydantic import BaseModel


class BlueEnablePrometheus(BaseModel):
    callbackURL: str
    operation: Literal['monitor']
