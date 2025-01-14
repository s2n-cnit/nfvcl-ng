from ipaddress import AddressValueError
from pathlib import Path
from typing import Optional, Type, Tuple

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource

from pydantic import field_validator, Field, BaseModel

from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.network.ipam_models import SerializableIPv4Address


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
        try:
            SerializableIPv4Address(ip)
        except AddressValueError as e:
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


class RedisParameters(BaseModel):
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


class NFVCLConfigModel(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NFVCL_", env_nested_delimiter="_")

    log_level: int = Field(default=20, description="10 = DEBUG, CRITICAL = 50,FATAL = CRITICAL, ERROR = 40, WARNING = 30, WARN = WARNING, INFO = 20, DEBUG = 10, NOTSET = 0")
    nfvcl: NFVCLParameters = Field(default_factory=NFVCLParameters)
    mongodb: MongoParameters = Field(default_factory=NFVCLParameters)
    redis: RedisParameters = Field(default_factory=NFVCLParameters)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return env_settings, init_settings

def load_nfvcl_config() -> NFVCLConfigModel:
    """
    Read the NFVCL config from the configuration file. If config/config_dev.yaml is present, this function load from this file,
    otherwise the function reads the default config/config.yaml

    Returns:
        The NFVCL configuration
    """
    print("load_nfvcl_config")
    dev_config_file_path = Path("config/config_dev.yaml")
    default_config_file_path = Path("config/config.yaml")
    # Loading develops nfvcl file if present (Not uploaded on Git)
    config_file_path = dev_config_file_path if dev_config_file_path.is_file() else default_config_file_path

    with open(config_file_path, 'r') as stream_file:
        # pre_config_logger.info(f"Loading config from {config_file_path.name}")
        config: NFVCLConfigModel
        try:
            nfvcl_conf = yaml.safe_load(stream_file)
        except yaml.YAMLError as exc:
            # pre_config_logger.exception("Error loading config", exc)
            pass

        # Parsing the config file
        try:
            config = NFVCLConfigModel(**nfvcl_conf)
        except Exception as exce:
            # pre_config_logger.exception("Exception in the configuration file parsing", exce)
            pass
        return config

