import base64
import logging
import os
import string
import random
from typing import List
import OpenSSL
import yaml
from OpenSSL.crypto import PKey
from jinja2 import Environment, FileSystemLoader
from models.config_model import NFVCLConfigModel

# Using _ before name such that cannot be directly accessed from external files.
_nfvcl_config: NFVCLConfigModel

# TODO remove this code as soon as all reference to this variables are removed. Use the next function
with open("config.yaml", 'r') as stream:
    try:
        nfvcl_conf = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)

    # Parsing the config file
    try:
        nfvcl_ip = nfvcl_conf['nfvcl']['ip']
        nfvcl_port = str(nfvcl_conf['nfvcl']['port'])

        osm_ip = nfvcl_conf['osm']['host']
        osm_port = str(nfvcl_conf['osm']['port'])
        osm_user = nfvcl_conf['osm']['username']
        osm_passwd = nfvcl_conf['osm']['password']
        osm_proj = nfvcl_conf['osm']['project']
        if 'version' in nfvcl_conf['osm']:
            if nfvcl_conf['osm']['version'] > 8:
                sol006 = True

        mongodb_host = nfvcl_conf['mongodb']['host']
        mongodb_port = str(nfvcl_conf['mongodb']['port'])
        mongodb_db = nfvcl_conf['mongodb']['db']
        redis_host = nfvcl_conf['redis']['host']
        redis_port = str(nfvcl_conf['redis']['port'])
    except Exception as exception:
        print('exception in the configuration file parsing: {}'.format(str(exception)))


def get_nfvcl_config() -> NFVCLConfigModel:
    """
    Returning existing config or generating new one in case it is None

    Returns:
        The NFVCL config
    """
    global _nfvcl_config

    # Using _nfvcl_config is present
    if '_nfvcl_config' in globals():
        # If none, generate new one. Else return existing one
        if _nfvcl_config is None:
            _nfvcl_config = load_nfvcl_config()
            return _nfvcl_config
        else:
            return _nfvcl_config
    # In case there is a problem reading and returning the config
    return load_nfvcl_config()


def load_nfvcl_config() -> NFVCLConfigModel:
    """
    Read the NFVCL config from the configuration file. If config_dev.yaml is present, this function load from this file,
    otherwise the function read the default config.yaml

    Returns:
        The NFVCL configuration
    """
    # Loading develop nfvcl file if present (Not uploaded on Git)
    if os.path.exists("config_dev.yaml"):
        config_file = open("config_dev.yaml", 'r')
    else:
        config_file = open("config.yaml", 'r')

    with config_file as stream:
        config: NFVCLConfigModel
        try:
            nfvcl_conf = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

        # Parsing the config file
        try:
            config = NFVCLConfigModel.parse_obj(nfvcl_conf)
        except Exception as exce:
            print('exception in the configuration file parsing: {}'.format(exce))
        return config


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def create_logger(name: str) -> logging.getLogger:
    # create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)
    return logger


# Class decorator for locking methods
def obj_multiprocess_lock(func):
    def wrapper(self, *args, **kwargs):
        print("acquiring lock")
        self.lock.acquire()
        print("acquired lock")

        r = func(self, *args, **kwargs)

        print("releasing lock")
        self.lock.release()
        print("released lock")
        return r

    return wrapper


def deprecated(func):
    """
    Deprecated decorator. When a function is tagged with this decorator, every time the function is called, it prints
    that the function is deprecated.
    """

    def wrapper(*args, **kwargs):
        print('Function', func.__name__, 'is deprecated.')
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
