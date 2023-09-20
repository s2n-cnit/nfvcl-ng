from typing import Union
from pydantic import BaseModel
from models.blueprint.blue_events import BlueEventType
from models.k8s.k8s_events import K8sEventType
from topology.topology_events import TopologyEventType


class Event(BaseModel):
    operation: Union[TopologyEventType, BlueEventType, K8sEventType]
    data: dict

    def __init__(self, operation, data: dict) -> None:
        super().__init__(operation=operation, data=data)

