from pydantic import BaseModel, AnyHttpUrl


class RestAnswer202(BaseModel):
    id: str
    description: str ='operation submitted'
    status: str ='submitted'


class CallbackModel(BaseModel):
    id: str
    operation: str
    status: str
    detailed_status: str


class CallbackRequest(BaseModel):
    callback: AnyHttpUrl = None
