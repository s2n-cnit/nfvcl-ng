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
        logger = create_logger("Util")
    return _nfvcl_config


def _load_nfvcl_config() -> NFVCLConfigModel:
    """
    Read the NFVCL config from the configuration file. If config_dev.yaml is present, this function load from this file,
    otherwise the function read the default config.yaml

    Returns:
        The NFVCL configuration
    """

    dev_config_file_path = Path("config_dev.yaml")
    default_config_file_path = Path("config.yaml")
    # Loading develop nfvcl file if present (Not uploaded on Git)
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


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def obj_multiprocess_lock(func):
    """
    Class decorator for locking methods that edit topology information
    Semaphore for topology. Locks the topology such that only ONE operation is made at the same time.
    """
    def wrapper(self, *args, **kwargs):
        logger.debug("Acquiring lock")
        self.lock.acquire()
        logger.debug("Acquired lock")

        # In case of crash we still need to unlock the semaphore -> TRY
        try:
            #
            response = func(self, *args, **kwargs)
            logger.debug("Releasing lock")
            self.lock.release()
            logger.debug("Released lock")
            return response
        except Exception as excep:
            # In case of crash we still need to unlock the semaphore
            self.lock.release()
            raise excep

    return wrapper


def deprecated(func):
    """
    Deprecated decorator. When a function is tagged with this decorator, every time the function is called, it prints
    that the function is deprecated.
    """

    def wrapper(*args, **kwargs):
        logger.warning(f"Function {func.__name__} is deprecated.")
        return func(*args, **kwargs)

    return wrapper


def render_file_from_template(path: str, render_dict: dict, prefix_to_name: str = "") -> str:
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

    new_name = prefix_to_name + '_' + filename

    with open('day2_files/' + new_name, 'w') as file:
        file.write(data)
        file.close()

    return file.name


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
        to_return.append(render_file_from_template(path=file_path, render_dict=render_dict,
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
