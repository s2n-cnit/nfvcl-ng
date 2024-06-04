from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
from bson import ObjectId
import datetime

class PyObjectId(ObjectId):

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError('Invalid objectid')
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type='string')


class DbBlue(BaseModel):
    #id: Optional[PyObjectId] = Field(alias='_id')
    id: str
    conf: dict
    input_conf: Optional[dict] = Field(default=None)
    nsd_: Optional[List[Dict]] = Field(default=[])
    pdu: Optional[List[str]] = Field(default=None)
    vnfd: Optional[Dict[str, Any]]
    # self.vnf_configurator = []
    primitives: Optional[List[dict]] = Field(default=[])
    action_to_check: Optional[List[dict]] = Field(default=[])
    timestamp: Dict[str, datetime.datetime] = Field(default={})
    config_len: dict = Field(default={})
    created: datetime.datetime
    status: str = "bootstraping"
    detailed_status: Union[str, None] = Field(default="")
    current_operation: Union[str, None] = Field(default="")
    modified: Optional[datetime.datetime] = Field(default=None)
    supported_operations: Dict[str, List]
    type: str


    """class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str
        }
"""