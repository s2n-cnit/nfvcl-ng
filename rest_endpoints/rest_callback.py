from pydantic import BaseModel, AnyHttpUrl, Field


class RestAnswer202(BaseModel):
    id: str
    operation_type: str = Field(default="", description="The requested operation")
    description: str = 'operation submitted'
    status: str = 'submitted'


class CallbackModel(BaseModel):
    id: str
    operation: str
    status: str
    detailed_status: str


class CallbackRequest(BaseModel):
    callback: AnyHttpUrl = None
