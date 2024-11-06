import re
import datetime
from enum import Enum
from pydantic import BaseModel, field_validator, Field

from nfvcl.models.base_model import NFVCLBaseModel


class RTRRestAnswer(BaseModel):
    description: str = 'operation submitted'
    status: str = 'submitted'
    status_code: int = 202  # OK
    data: dict = {}


class RTRActionType(str, Enum):
    DNS_RATE_LIMIT = "DNS_RATE_LIMIT"
    DNS_SERV_DISABLE = "DNS_SERV_DISABLE"
    DNS_SERV_ENABLE = "DNS_SERV_ENABLE"
    TEST = "TEST"


class DOCActionDNSstatus(NFVCLBaseModel):
    Zone: str
    Status: str


class DOCActionDNSLimit(NFVCLBaseModel):
    Zone: str
    Rate: int

    @field_validator('Rate', mode='before')
    @classmethod
    def validate_limit(cls, limit: str):
        try:
            return int(limit)
        except ValueError:
            match = re.match("[0-9]*", limit)
            if match:
                return match.group(0)
            else:
                raise ValueError(f"Invalid limit value in the request: {limit}. Cannot parse. Value should be an integer or '12434/s' or '12331 /s'.")


class DOCActionDefinition(NFVCLBaseModel):
    ActionType: str
    Service: str
    Action: dict


class DOCNorthModel(NFVCLBaseModel):
    ActionID: str
    Target: str
    ActionDefinition: DOCActionDefinition


class CallbackCode(int, Enum):
    ACTION_APPLIED_BY_EPEM = 200 # Similar to HTTP, 2XX is OK.
    ACTION_APPLIED_BY_DOC = 201
    ACTION_NOT_APPLIED_BY_EPEM = 400 # Similar to HTTP, 4XX is Error.
    ACTION_NOT_APPLIED_BY_DOC = 401

class CallbackModel(NFVCLBaseModel):
    actionid: str = Field(description="Action ID used to identify the action that has been completed")
    code: CallbackCode = Field(description="Code used to identify the status of the performed action")
    description: str = Field(description="Description of the application of the mitigation. Describe why it has been or not applied")
    timestamp: str = Field(description="Timestamp when the action/mitigation has been completed", default_factory=lambda: str(datetime.datetime.now()))
