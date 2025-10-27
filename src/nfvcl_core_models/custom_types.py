from typing import Annotated
from pydantic import Field
from nfvcl_common.utils.util import IP_OR_HOST_PATTERN

AreaIDType = Annotated[int, Field(gt=0, lt=65000)]
IPHostType = Annotated[str, Field(pattern=IP_OR_HOST_PATTERN, examples=["192.168.1.1", "host.example.com"])]

class NFVCLCoreException(Exception):
    http_equivalent_code: int
    message: str

    def __init__(self, message: str = "", http_equivalent_code: int = 500):
        self.message = message
        self.http_equivalent_code = http_equivalent_code
        super().__init__(self.message)
