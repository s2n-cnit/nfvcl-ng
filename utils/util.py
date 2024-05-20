import base64
import os
import string
import random
import glob
from logging import Logger
from pathlib import Path
from typing import List
import OpenSSL
import yaml
import shutil
from models.config_model import NFVCLConfigModel
from OpenSSL.crypto import PKey
from jinja2 import Environment, FileSystemLoader

IP_PORT_PATTERN: str = '^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$'
IP_PATTERN: str = '^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
PORT_PATTERN: str = '^([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$'
PATH_PATTERN: str = '^[\/]([^\/\s]+\/)+'

# Using _ before name such that cannot be directly accessed from external files.
_nfvcl_config: NFVCLConfigModel | None = None


def is_config_loaded() -> bool:
    global _nfvcl_config
    return _nfvcl_config is not None


from utils.log import create_logger
pre_config_logger = create_logger("PreConfig")
logger: Logger | None = None


def get_nfvcl_config() -> NFVCLConfigModel:
    """
    Returning existing config or generating new one in case it is None

    Returns:
        The NFVCL config
    """
    global _nfvcl_config, logger

    # Using _nfvcl_config is present
    if not _nfvcl_config:
        _nfvcl_config = _load_nfvcl_config()
        logger = create_logger("Util", ov_log_level=_nfvcl_config.log_level)
    return _nfvcl_config


def _load_nfvcl_config() -> NFVCLConfigModel:
    """
    Read the NFVCL config from the configuration file. If config_dev.yaml is present, this function load from this file,
    otherwise the function reads the default config.yaml

    Returns:
        The NFVCL configuration
    """

    dev_config_file_path = Path("config_dev.yaml")
    default_config_file_path = Path("config.yaml")
    # Loading develops nfvcl file if present (Not uploaded on Git)
    config_file_path = dev_config_file_path if dev_config_file_path.is_file() else default_config_file_path

    with open(config_file_path, 'r') as stream_file:
        pre_config_logger.info(f"Loading config from {config_file_path.name}")
        config: NFVCLConfigModel
        try:
            nfvcl_conf = yaml.safe_load(stream_file)
        except yaml.YAMLError as exc:
            pre_config_logger.exception("Error loading config", exc)

        # Parsing the config file
        try:
            config = NFVCLConfigModel.model_validate(nfvcl_conf)
        except Exception as exce:
            pre_config_logger.exception("Exception in the configuration file parsing", exce)
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


# TODO move to Path, not use str
def render_file_from_template_to_file(path: str, render_dict: dict, prefix_to_name: str = "") -> str:
    """
    Render a template file using the render_dict dictionary. Use the keys and their values to give a value at the
    variables present in the template file.
    The result of the rendering is placed in day2_files/filename.extension and the path is returned by this method.

    Args:
        path: the path of the file template

        render_dict: the dictionary containing values to be used in template variables. The name of the variable should
        be the same of the key in this dictionary.

        prefix_to_name: A prefix to be appended to generated file.

    Returns:
        the path of the generated file from the template.
    """
    env_path = ""
    for folder in path.split('/')[:-1]:
        env_path += "{}/".format(folder)
    filename = path.split('/')[-1]
    env = Environment(loader=FileSystemLoader(env_path),
                      extensions=['jinja2_ansible_filters.AnsibleCoreFiltersExtension'])
    template = env.get_template(filename)
    data = template.render(confvar=render_dict)

    if prefix_to_name == "":
        new_name = filename
    else:
        new_name = prefix_to_name + '_' + filename

    with open('day2_files/' + new_name, 'w') as file:
        file.write(data)
        file.close()

    return file.name

def render_file_jinja2_to_str(file_to_render: Path, confvar: dict):
    """
    Takes a file and renders it using values in the dictionary
    Args:
        playbook_file: The file to be rendered containing '{{ variable123 }}' references
        confvar: A dictionary containing the variables to be rendered. { 'variable123': 'desiredvalue' }

    Returns:
        The rendered file
    """
    env = Environment(loader=FileSystemLoader(file_to_render.parent))
    template = env.get_template(file_to_render.name)

    return template.render(**confvar)


def render_files_from_template(paths: List[str], render_dict, files_name_prefix: str = "TEST") -> List[str]:
    """
    Render multiple files from their templates. For further details looks at render_file_from_template function.
    Then the list of generated files (paths) is returned

    Args:
        paths: the list of file templates

        render_dict: the dictionary containing values to be used in template variables. The name of the variable should
        be the same of the key in this dictionary.

        files_name_prefix: A prefix to be appended to generated files.

    Returns:
        A list path representing generated files.
    """
    to_return: List[str] = []
    for file_path in paths:
        to_return.append(render_file_from_template_to_file(path=file_path, render_dict=render_dict,
                                                           prefix_to_name=files_name_prefix))
    return to_return


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


def remove_files_by_pattern(folder: str, name_pattern: str):
    """
    Remove all files in the target folder that match the pattern condition
    Args:
        folder: the folder in witch files are located. ("./day2_files" or "day2_files" or "/tmp/nsd_packages"

        name_pattern: a file name ("DV87AO_vyos_2-3.yaml") or a pattern for multiple files ("DV87AO_*")

    Returns:

    """
    source_path: str = "{}/{}".format(folder, name_pattern)
    path_list = glob.glob(source_path)
    for path in path_list:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def copytree(src, dst, symlinks=False, ignore=None):
    """
    TODO complete doc
    Args:
        src:
        dst:
        symlinks:
        ignore:

    Returns:

    """
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)



