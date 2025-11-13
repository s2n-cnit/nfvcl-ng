from typing import Any, Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel

class BlueprintOperationCallbackModel(NFVCLBaseModel):
    id: str = Field()
    operation: str = Field()
    status: str = Field()
    result: Optional[Any] = Field(default=None)
    detailed_status: Optional[str] = Field(default=None)
