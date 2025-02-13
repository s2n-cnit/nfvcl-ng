from typing import Annotated
from pydantic import Field
from nfvcl_core.utils.util import IP_OR_HOST_PATTERN

AreaIDType = Annotated[int, Field(gt=0, lt=65000)]
IPHostType = Annotated[str, Field(pattern=IP_OR_HOST_PATTERN, examples=["192.168.1.1", "host.example.com"])]
