import socket

from nfvcl.models.base_model import NFVCLBaseModel
from pydantic import field_validator

from nfvcl.utils.ipam import check_ipv4_valid


class NFVCLParameters(NFVCLBaseModel):
    version: str
    ip: str
    port: int

    @field_validator('ip')
    @classmethod
    def validate_ip(cls, ip: str):
        if ip is None or len(ip) == 0:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # doesn't even have to be reachable
                s.connect(('192.255.255.255', 1))
                IP = s.getsockname()[0]
            except:
                IP = '0.0.0.0'
            finally:
                s.close()
            return IP
        else:
            if not check_ipv4_valid(ip):
                raise ValueError(f">{ip}< is not a valid IPv4 address.")
            return ip


class OSMParameters(NFVCLBaseModel):
    host: str
    port: str
    username: str
    password: str
    project: str
    version: int


class MongoParameters(NFVCLBaseModel):
    host: str
    port: int
    db: str


class RedisParameters(NFVCLBaseModel):
    host: str
    port: int


class BlueDescription(NFVCLBaseModel):
    class_name: str
    module_name: str


class NFVCLConfigModel(NFVCLBaseModel):
    log_level: int
    nfvcl: NFVCLParameters
    osm: OSMParameters
    mongodb: MongoParameters
    redis: RedisParameters
