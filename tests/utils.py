import socket
from typing import Optional

import paramiko

from models.config_unitest import ConfigUniteTest
from nfvcl_core.utils.blue_utils import get_yaml_parser

unittest_config: Optional[ConfigUniteTest] = None

def get_unittest_config() -> ConfigUniteTest:
    global unittest_config
    if unittest_config is None:
        parser = get_yaml_parser()
        with open("config_unitest_dev.yaml", 'r') as stream:
            data_loaded = parser.load(stream)
            unittest_config = ConfigUniteTest.model_validate(data_loaded)
    return unittest_config


class SSH:
    def __init__(self, ip, user=None, passwd=None):
        self.pwd = passwd if passwd else "ubuntu"
        self.user = user if user else "ubuntu"
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(ip,
                         port=22, username=self.user,
                         password=self.pwd, timeout=3)

    def get_file_content(self, path: str):
        _, stdout, _ = self.ssh.exec_command(f"cat {path}")
        stdout = ' '.join(stdout.readlines())
        return stdout

    def execute_ssh_command(self, command: str, sudo=False):
        command = f"echo {self.pwd} | sudo -S {command}" if sudo else command
        stdin, stdout, stderr = self.ssh.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            raise Exception(f"Error executing command: {command}")
        else:
            return stdout

    def close_connection(self):
        self.ssh.close()


def check_tcp_server(address, port):
    timeout = 40  # timeout in seconds
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((address, port))
        s.close()
        return True
    except Exception as e:
        print(e)
        s.close()
        return False
