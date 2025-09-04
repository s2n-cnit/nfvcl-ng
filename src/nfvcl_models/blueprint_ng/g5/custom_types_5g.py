import re
from enum import IntEnum, Enum
from typing import Annotated, TYPE_CHECKING, Any

from pydantic import Field, BeforeValidator, GetCoreSchemaHandler
from pydantic._internal import _schema_generation_shared
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

from nfvcl_core.utils.util import HOSTNAME_PATTERN


def sst_str_to_int(v: object) -> object:
    if isinstance(v, str):
        if v.startswith("0x"):
            return int(v[2:], 16)
        if v not in SSTEnum.__members__:
            raise ValueError(f"Invalid value for sst: {v}")
        return SSTEnum[v].value
    return v

def sd_uniform(v: object) -> object:
    if isinstance(v, int):
        return f"{v:06X}"
    if not isinstance(v, str):
        raise ValueError(f"Invalid value for sd: {v}")
    if v.startswith("0x"):
        v = v[2:]
    return v.upper()

SDType = Annotated[
    str,
    Field(pattern=r"^([A-F0-9]{6})$", examples=["000001"], description="Slice Differentiator in hex format: 000001-FFFFFF"),
    BeforeValidator(sd_uniform)
]

class SSTEnum(IntEnum):
    EMBB  = 1 # Enhanced Mobile Broadband
    URLLC = 2 # Ultra-Reliable Low Latency Communication
    MIOT  = 3 # Massive Internet of Things
    V2X   = 4 # Vehicle to Everything
    HMTC  = 5 # High-Performance Machine-Type Communications

SSTType = Annotated[
    SSTEnum,
    Field(gt=0, lt=256, description="Slice Service Type, can be an int or a string (between: EMBB, URLLC, MIOT, V2X, HMTC)"),
    BeforeValidator(sst_str_to_int)
]

class PDUSessionType(str, Enum):
    IPv4 = "IPv4"
    IPv6 = "IPv6"

DNNType = Annotated[str, Field(pattern=HOSTNAME_PATTERN, description="Data Network Name")]
IMSIType = Annotated[str, Field(pattern=r'^[0-9]*$', min_length=15, max_length=15, description="IMSI")]
SUPIType = Annotated[str, Field(pattern=r'^imsi-[0-9]*$', min_length=20, max_length=20, description="SUPI")]
PLMNType = Annotated[str, Field(pattern=r'^[0-9]*$', min_length=5, max_length=5, description="PLMN")]
MCCType = Annotated[str, Field(pattern=r'^[0-9]*$', min_length=3, max_length=3, description="MCC")]
MNCType = Annotated[str, Field(pattern=r'^[0-9]*$', min_length=2, max_length=2, description="MNC")]
KEYType = Annotated[str, Field(pattern=r'^[a-fA-F0-9]+$', min_length=32, max_length=32, description="KEY")]
OPCType = Annotated[str, Field(pattern=r'^[a-fA-F0-9]+$', min_length=32, max_length=32, description="OPC")]

if TYPE_CHECKING:
    BitrateString = Annotated[str, ...]
else:
    class BitrateString(str):
        @classmethod
        def __get_pydantic_core_schema__(
            cls,
            _source: type[Any],
            _handler: GetCoreSchemaHandler,
        ) -> core_schema.CoreSchema:
            return core_schema.no_info_after_validator_function(cls._validate, core_schema.str_schema())

        @classmethod
        def __get_pydantic_json_schema__(
            cls, core_schema: core_schema.CoreSchema, handler: _schema_generation_shared.GetJsonSchemaHandler
        ) -> JsonSchemaValue:
            field_schema = handler(core_schema)
            field_schema.update(type='string')
            return field_schema

        @classmethod
        def _validate(cls, input_value: str, /) -> str:
            if not re.match(r"^\d+\s(bps|kbps|Mbps|Gbps)$", input_value):
                raise ValueError(f"Invalid bitrate format: {input_value}")
            return input_value

        def get_numeric(self) -> int:
            return int(self.split(" ")[0])

        def get_unit(self) -> str:
            return self.split(" ")[1]

        def to_bps(self) -> int:
            value, unit = self.get_numeric(), self.get_unit().lower()
            conversion_factors = {"bps": 1, "kbps": 1_000, "mbps": 1_000_000, "gbps": 1_000_000_000}
            return value * conversion_factors[unit]

        def to_kbps(self) -> float:
            return self.to_bps() / 1_000

        def to_mbps(self) -> float:
            return self.to_bps() / 1_000_000

        def to_gbps(self) -> float:
            return self.to_bps() / 1_000_000_000

        def to_kbps_int(self) -> int:
            return self.to_bps() // 1_000

        def to_mbps_int(self) -> int:
            return self.to_bps() // 1_000_000

        def to_gbps_int(self) -> int:
            return self.to_bps() // 1_000_000_000


BitrateStringType = Annotated[BitrateString, Field(pattern=r"^\d+\s(bps|kbps|Mbps|Gbps)$" ,description="Bitrate in the format: <value> <unit> (e.g. 100 Mbps), allowed units: bps, kbps, Mbps, Gbps")]
