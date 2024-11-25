import base64
import os
import string
import random
from pathlib import Path
import OpenSSL
import yaml
from nfvcl.models.config_model import NFVCLConfigModel
from OpenSSL.crypto import PKey

IP_PORT_PATTERN: str = '^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$'
IP_PATTERN: str = '^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
PORT_PATTERN: str = '^([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$'
PATH_PATTERN: str = '^[\/]([^\/\s]+\/)*[^\/\s]*'
PATH_PATTERN_FINAL_SLASH: str = '^[\/]([^\/\s]+\/)+'

# Using _ before name such that cannot be directly accessed from external files.
_nfvcl_config: NFVCLConfigModel | None = None


def is_config_loaded() -> bool:
    global _nfvcl_config
    return _nfvcl_config is not None


# from nfvcl.utils.log import create_logger
# pre_config_logger = create_logger("PreConfig")
# logger: Logger | None = None

def check_conf_env_variables(_nfvcl_config: NFVCLConfigModel) -> NFVCLConfigModel:
    """
    If variables are present, override configuration parameters loaded from the file with ENV values
    Args:
        _nfvcl_config: The configuration loaded from the file

    Returns:
        The overwritten configuration.
    """
    if os.getenv('MONGO_IP'): _nfvcl_config.mongodb.host = os.getenv('MONGO_IP')
    if os.getenv('MONGO_PORT'): _nfvcl_config.mongodb.port = os.getenv('MONGO_PORT')
    if os.getenv('MONGO_USR'): _nfvcl_config.mongodb.username = os.getenv('MONGO_USR')
    if os.getenv('MONGO_PWD'): _nfvcl_config.mongodb.password = os.getenv('MONGO_PWD')
    if os.getenv('REDIS_IP'): _nfvcl_config.redis.host = os.getenv('REDIS_IP')
    if os.getenv('REDIS_PORT'): _nfvcl_config.redis.port = os.getenv('REDIS_PORT')
    if os.getenv('NFVCL_IP'): _nfvcl_config.nfvcl.ip = os.getenv('NFVCL_IP')
    if os.getenv('NFVCL_PORT'): _nfvcl_config.nfvcl.port = os.getenv('NFVCL_PORT')
    return _nfvcl_config


def get_nfvcl_config() -> NFVCLConfigModel:
    """
    Returning existing config or generating new one in case it is None

    Returns:
        The NFVCL config
    """
    global _nfvcl_config

    # Using _nfvcl_config is present
    if not _nfvcl_config:
        _nfvcl_config = check_conf_env_variables(_load_nfvcl_config())
        # logger = create_logger("Util", ov_log_level=_nfvcl_config.log_level)
    return _nfvcl_config


def _load_nfvcl_config() -> NFVCLConfigModel:
    """
    Read the NFVCL config from the configuration file. If config/config_dev.yaml is present, this function load from this file,
    otherwise the function reads the default config/config.yaml

    Returns:
        The NFVCL configuration
    """

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
            config = NFVCLConfigModel.model_validate(nfvcl_conf)
        except Exception as exce:
            # pre_config_logger.exception("Exception in the configuration file parsing", exce)
            pass
        return config


def generate_id(length: int = 6, character_set: str = string.ascii_uppercase + string.digits) -> str:
    """
    Generate random ID given the length and the character set.
    Args:
        length: The length of the generated ID
        character_set: The character set to be used.

    Returns:
        The random ID (str)
    """
    return ''.join(random.choice(character_set) for _ in range(length))


def generate_blueprint_id() -> str:
    """
    Generate blueprint random ID (6 digits) using characters in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'.

    Returns:
        The random 6-digit ID (str)
    """
    return generate_id(6, string.ascii_uppercase + string.digits)


def generate_rsa_key(length: int = 2048):
    """
    Generate an RSA key
    Args:
        length: The desired length of the key (default 2048)

    Returns:
        a couple (key, private_key), where the private_key is the dump of the private key
    """
    key: PKey = OpenSSL.crypto.PKey()
    key.generate_key(OpenSSL.crypto.TYPE_RSA, length)

    private_key = OpenSSL.crypto.dump_privatekey(
        OpenSSL.crypto.FILETYPE_PEM, key)

    return key, private_key


def generate_cert_sign_req(common_name: str, key: PKey):
    """
    Generate a certificate signing request (CSR) based on a RSA key.
    Args:
        common_name: The CN to be assigned at the certificate
        key: The base of the certificate

    Returns:
        The CSR
    """
    req = OpenSSL.crypto.X509Req()
    req.get_subject().CN = common_name
    req.set_pubkey(key)
    req.sign(key, 'sha256')

    csr = OpenSSL.crypto.dump_certificate_request(
        OpenSSL.crypto.FILETYPE_PEM, req)

    return csr


def convert_to_base64(content_bytes: bytes) -> str:
    """
    Convert bytes[] to base64
    Args:
        content_bytes: bytes to be converted in base 64

    Returns:
        The converted string
    """
    content_base64_bytes = base64.b64encode(content_bytes)
    content_base64 = content_base64_bytes.decode("ascii")

    return content_base64


def convert_from_base64(content: str) -> str:
    """
    Convert str in base64 format to ascii
    Args:
        content: bytes to be converted from base 64

    Returns:
        The converted string
    """
    content_bytes = base64.b64decode(content)
    content_str = content_bytes.decode("ascii")

    return content_str


def get_from_nested_dict(d, keys):
    if "." in keys:
        key, rest = keys.split(".", 1)
        return get_from_nested_dict(d[key], rest)
    else:
        return d[keys]


def put_in_nested_dict(d, keys, item):
    if "." in keys:
        key, rest = keys.split(".", 1)
        if key not in d:
            d[key] = {}
        put_in_nested_dict(d[key], rest, item)
    else:
        d[keys] = item
