import socket
from typing import Optional

from nfvcl.models.base_model import NFVCLBaseModel
from pydantic import field_validator, Field

from nfvcl.utils.ipam import check_ipv4_valid


class NFVCLParameters(NFVCLBaseModel):
    version: str
    ip: str
    port: int
    mounted_folder: str = Field(default="mounted_folder", description="The folder in which files are generated to be exposed in API 'NFVCL_URL:NFVCL_PORT/files/'")
    tmp_folder: str = Field(default="/tmp/nfvcl", description="The folder in which the tmp files are saved")

    class Config:
        validate_assignment = True

    @field_validator('ip', mode='before')
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
    def validate_mongo_host(cls, host: int):
        if isinstance(host, str):
            return host
        raise ValueError(f"Config decode error for Mongo DB host: >{host}< is not a valid string.")

    @field_validator('db', mode='before')
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
    def validate_redis_host(cls, host: int):
        if isinstance(host, str):
            return host
        raise ValueError(f"Config decode error for Redis DB host: >{host}< is not a valid string.")


class NFVCLConfigModel(NFVCLBaseModel):
    log_level: int = Field(default=20, description="10 = DEBUG, CRITICAL = 50,FATAL = CRITICAL, ERROR = 40, WARNING = 30, WARN = WARNING, INFO = 20, DEBUG = 10, NOTSET = 0")
    nfvcl: NFVCLParameters
    mongodb: MongoParameters
    redis: RedisParameters

    class Config:
        validate_assignment = True
