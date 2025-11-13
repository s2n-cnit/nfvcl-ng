from ipaddress import AddressValueError
from pathlib import Path
from typing import Optional, Type, Tuple

import yaml
from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.config import MongoParameters
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address


class NFVCLProvidersParameters(NFVCLBaseModel):
    ip: str
    port: int
    workers: int = Field(default=4, description="The number of workers to handle the requests")
    tmp_folder: str = Field(default="/tmp/nfvcl", description="The folder in which the tmp files are saved")
    admin_uuid: str = Field(description="The admin UUID to be used to authenticate the requests")

    class Config:
        validate_assignment = True

    @field_validator('ip', mode='before')
    def validate_ip(cls, ip: str):
        try:
            SerializableIPv4Address(ip)
        except AddressValueError:
            raise ValueError(f">{ip}< is not a valid IPv4 address.")
        return ip

    @field_validator('port', mode='before')
    def validate_port(cls, port: int):
        if isinstance(port, str):
            try:
                port = int(port)
            except ValueError:
                raise ValueError(f"Config decode error for NFVCL PORT: >{port}< cannot be converted to int.")
        elif not isinstance(port, int):
            raise ValueError(f"Config decode error for NFVCL PORT: >{port}< must be str or int.")
        return port

class NFVCLProvidersConfigModel(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NFVCL_PROVIDERS_", env_nested_delimiter="_")

    log_level: int = Field(default=20, description="10 = DEBUG, CRITICAL = 50,FATAL = CRITICAL, ERROR = 40, WARNING = 30, WARN = WARNING, INFO = 20, DEBUG = 10, NOTSET = 0")
    nfvcl_providers: NFVCLProvidersParameters = Field(default_factory=NFVCLProvidersParameters)
    mongodb: MongoParameters = Field(default_factory=MongoParameters)

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

def load_nfvcl_providers_config(path: Optional[str] = None) -> NFVCLProvidersConfigModel:
    """
    Read the NFVCL config from the configuration file. If config/config_dev.yaml is present, this function load from this file,
    otherwise the function reads the default config/config.yaml

    Returns:
        The NFVCL configuration
    """
    print("load_nfvcl_config")
    if path:
        config_file_path = Path(path)
    else:
        dev_config_file_path = Path("config/providers_rest/config_dev.yaml")
        default_config_file_path = Path("config/providers_rest/config.yaml")
        # Loading develops nfvcl file if present (Not uploaded on Git)
        config_file_path = dev_config_file_path if dev_config_file_path.is_file() else default_config_file_path

    with open(config_file_path, 'r') as stream_file:
        # pre_config_logger.info(f"Loading config from {config_file_path.name}")
        config: NFVCLProvidersConfigModel
        try:
            nfvcl_conf = yaml.safe_load(stream_file)
        except yaml.YAMLError as exc:
            # pre_config_logger.exception("Error loading config", exc)
            print("Error loading config", exc)
            exit(1)

        # Parsing the config file
        try:
            config = NFVCLProvidersConfigModel(**nfvcl_conf)
        except Exception as exce:
            # pre_config_logger.exception("Exception in the configuration file parsing", exce)
            print("Exception in the configuration file parsing", exce)
            exit(1)
        return config

