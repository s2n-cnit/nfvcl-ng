import paramiko
from paramiko.client import SSHClient
from paramiko.sftp_client import SFTPClient


def createSSHClient(server, port, user, password) -> SSHClient:
    client: SSHClient = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password, allow_agent=False)

    return client


def createSCPClient(server, port, user, password) -> SFTPClient:
    ssh: SSHClient = createSSHClient(server, port, user, password)
    scp: SFTPClient = ssh.open_sftp()
    return scp


def upload_file(client: SFTPClient, local_file_path: str, destination_file_path: str):
    client.put(local_file_path, destination_file_path)
