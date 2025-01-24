from pydantic import BaseModel, Field
from nfvcl_core.models.base_model import NFVCLBaseModel


class RestAnswer202(BaseModel):
    id: str
    operation_type: str = Field(default="", description="The requested operation")
    description: str = 'operation submitted'
    status: str = 'submitted'


class CallbackModel(BaseModel):
    # id: str
    # operation: str
    status: str
    detailed_status: str
    result: str


class NFVCLRestError(NFVCLBaseModel):
    error: str = Field(default="Internal server error")
    status_code: int = Field(default=500)
