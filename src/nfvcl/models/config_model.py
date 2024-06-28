import socket
from typing import Optional

from nfvcl.models.base_model import NFVCLBaseModel
from pydantic import field_validator

from nfvcl.utils.ipam import check_ipv4_valid


class NFVCLParameters(NFVCLBaseModel):
    version: str
    ip: str
    port: int

    class Config:
        validate_assignment = True

    @field_validator('ip', mode='before')
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

    @field_validator('port', mode='before')
    @classmethod
    def validate_port(cls, port: int):
        if isinstance(port, str):
            try:
                port = int(port)
            except ValueError:
                raise ValueError(f"Config decode error for Mongo PORT: >{port}< cannot be converted to int.")
        elif not isinstance(port, int):
            raise ValueError(f"Config decode error for Mongo PORT: >{port}< must be str or int.")
        return port


class MongoParameters(NFVCLBaseModel):
    host: str
    port: int
    db: str
    username: Optional[str] = None
    password: Optional[str] = None

    class Config:
        validate_assignment = True

    @field_validator('port', mode='before')
    @classmethod
    def validate_mongo_port(cls, port: int):
        if isinstance(port, str):
            try:
                port = int(port)
            except ValueError:
                raise ValueError(f"Config decode error for Mongo PORT: >{port}< cannot be converted to int.")
        elif not isinstance(port, int):
            raise ValueError(f"Config decode error for Mongo PORT: >{port}< must be str or int.")
        return port

    @field_validator('host', mode='before')
    @classmethod
    def validate_mongo_host(cls, host: int):
        if isinstance(host, str):
            return host
        raise ValueError(f"Config decode error for Mongo DB host: >{host}< is not a valid string.")

    @field_validator('db', mode='before')
    @classmethod
    def check_parameters(cls, db):
        if not isinstance(db, str):
            raise ValueError(f"Config decode error for Mongo DB name: >{db}< is not a valid string.")
        return db


class RedisParameters(NFVCLBaseModel):
    host: str
    port: int

    class Config:
        validate_assignment = True

    @field_validator('port', mode='before')
    @classmethod
    def validate_redis_port(cls, port: int):
        if isinstance(port, str):
            try:
                port = int(port)
            except ValueError:
                raise ValueError(f"Config decode error for Redis PORT: >{port}< cannot be converted to int.")
        elif not isinstance(port, int):
            raise ValueError(f"Config decode error for Redis PORT: >{port}< must be str or int.")
        return port

    @field_validator('host', mode='before')
    @classmethod
    def validate_redis_host(cls, host: int):
        if isinstance(host, str):
            return host
        raise ValueError(f"Config decode error for Redis DB host: >{host}< is not a valid string.")


class NFVCLConfigModel(NFVCLBaseModel):
    log_level: int
    nfvcl: NFVCLParameters
    mongodb: MongoParameters
    redis: RedisParameters

    class Config:
        validate_assignment = True
