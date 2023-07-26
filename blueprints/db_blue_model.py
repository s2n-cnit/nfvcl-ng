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
    input_conf: Optional[dict]
    nsd_: Optional[List[Dict]] = []
    pdu: Optional[List[str]]
    vnfd: Optional[Dict[str, Any]]
    # self.vnf_configurator = []
    primitives: Optional[List[dict]] = []
    action_to_check: Optional[List[dict]] = []
    timestamp: Dict[str, datetime.datetime] = {}
    config_len: dict = {}
    created: datetime.datetime
    status: str = "bootstraping"
    detailed_status: Union[str, None] = ""
    current_operation: Union[str, None] = ""
    modified: Optional[datetime.datetime]
    supported_operations: Dict[str, List]
    type: str


    """class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str
        }
"""