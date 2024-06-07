from logging import Logger

import paramiko
from paramiko.client import SSHClient
from paramiko.sftp_client import SFTPClient

from nfvcl.utils.log import create_logger

logger: Logger = create_logger('SSH utils')


def create_ssh_Client(server, port, user, password) -> SSHClient:
    """
    Creates an SSH client for a remote server.
    The client can be used to operate on the server with SFTP, for example.
    Args:
        server: The IP of the server
        port: The port of the SSH server
        user: Username to be used when authenticate
        password: The password of the user

    Returns:
        The SSHClient
    """
    logger.debug(f"Creating SSH client - {server}:{port} for user {user} and pwd '{password}'")
    client: SSHClient = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password, allow_agent=False)

    return client


def createSCPClient(server, port, user, password) -> SFTPClient:
    """
    Creates an SFTP client for file transfer. It uses an SSH client to build a SFTP client.
    Args:
        server: The IP of the server
        port: The Port on witch the server is listening
        user: The user to be used for authentication
        password: The password of the user

    Returns:
        An SFTP client
    """
    ssh: SSHClient = create_ssh_Client(server, port, user, password)
    scp: SFTPClient = ssh.open_sftp()
    return scp


def upload_file(client: SFTPClient, local_file_path: str, destination_file_path: str):
    """
    Upload a file from a local folder to the remote location.
    Args:
        client: The SSH client to be used
        local_file_path: The path of the file, global path is suggested.
        destination_file_path: The global path or the relative path from the user home folder. ('file.yaml' will be put in '/home/user/file.yaml')

    Returns:
        an `.SFTPAttributes` object containing attributes about the given file
    """
    logger.debug(f"Uploading file '{local_file_path}' to '{destination_file_path}'")
    client.put(local_file_path, destination_file_path)
