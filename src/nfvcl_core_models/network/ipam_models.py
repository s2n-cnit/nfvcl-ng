from typing import Annotated
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network
from pydantic import PlainSerializer, Field

from nfvcl_core_models.base_model import NFVCLBaseModel

SerializableIPv4Address = Annotated[IPv4Address, PlainSerializer(lambda x: f'{x.exploded}', return_type=str, when_used='always')]
SerializableIPv4Network = Annotated[IPv4Network, PlainSerializer(lambda x: f'{x.exploded}', return_type=str, when_used='always')]
SerializableIPv6Address = Annotated[IPv6Address, PlainSerializer(lambda x: f'{x.exploded}', return_type=str, when_used='always')]
SerializableIPv6Network = Annotated[IPv6Network, PlainSerializer(lambda x: f'{x.exploded}', return_type=str, when_used='always')]

class EndPointV4(NFVCLBaseModel):
    ip: SerializableIPv4Address = Field(description="IPv4 address of the endpoint")
    port: int = Field(description="Port of the endpoint", le=65535, ge=1)

    def __str__(self) -> str:
        return f"{self.ip}:{self.port}"

    def __eq__(self, other):
        if isinstance(other, EndPointV4):
            return self.ip == other.ip and self.port == other.port
        return False
