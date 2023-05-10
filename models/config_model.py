from pydantic import BaseModel


class NFVCLParameters(BaseModel):
    ip: str
    port: str


class OSMParameters(BaseModel):
    host: str
    port: str
    username: str
    password: str
    project: str
    version: int


class MongoParameters(BaseModel):
    host: str
    port: str
    db: str


class RedisParameters(BaseModel):
    host: str
    port: str


class NFVCLConfigModel(BaseModel):
    nfvcl: NFVCLParameters

    osm: OSMParameters

    sol006: bool = True

    mongodb: MongoParameters

    redis: RedisParameters

