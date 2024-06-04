from typing import Literal
from pydantic import BaseModel


class BluePrometheus(BaseModel):
    callbackURL: str
    operation: Literal['monitor','disable_monitor']
    prom_server_id: str
