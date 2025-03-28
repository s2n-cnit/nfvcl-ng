from typing import Annotated
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network
from pydantic import PlainSerializer

SerializableIPv4Address = Annotated[IPv4Address, PlainSerializer(lambda x: f'{x.exploded}', return_type=str, when_used='always')]
SerializableIPv4Network = Annotated[IPv4Network, PlainSerializer(lambda x: f'{x.exploded}', return_type=str, when_used='always')]
SerializableIPv6Address = Annotated[IPv6Address, PlainSerializer(lambda x: f'{x.exploded}', return_type=str, when_used='always')]
SerializableIPv6Network = Annotated[IPv6Network, PlainSerializer(lambda x: f'{x.exploded}', return_type=str, when_used='always')]
