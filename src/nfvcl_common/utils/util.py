import base64
import string
import random
import OpenSSL
from OpenSSL.crypto import PKey

IP_PORT_PATTERN: str = R'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$'
IP_PATTERN: str = R'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
HOSTNAME_PATTERN = R"^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$"
IP_OR_HOST_PATTERN = f"({IP_PATTERN}|{HOSTNAME_PATTERN})"
PORT_PATTERN: str = R'^([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$'
PATH_PATTERN: str = R'^[\/]([^\/\s]+\/)*[^\/\s]*'
PATH_PATTERN_FINAL_SLASH: str = R'^[\/]([^\/\s]+\/)+'


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
