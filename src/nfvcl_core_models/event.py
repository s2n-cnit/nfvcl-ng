from typing import Union
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.event_types import K8sEventType, TopologyEventType, BlueEventType


class Event(NFVCLBaseModel):
    operation: Union[TopologyEventType, BlueEventType, K8sEventType]
    data: dict

    def __init__(self, operation, data: dict) -> None:
        super().__init__(operation=operation, data=data)

