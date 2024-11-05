import paramiko
import socket
import re
import time


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
        command = f"$ echo {self.pwd} | sudo -S {command}" if sudo else command
        stdin, stdout, stderr = self.ssh.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            raise Exception(f"Error executing command: {command}")
        else:
            return stdout

    def check_gnb_connection(self):
        timeout = time.time() + 60 * 1
        while True:
            stdout = self.execute_ssh_command(f"journalctl -u ueransim-gnb.service -b", sudo=True)
            output = ' '.join(stdout.readlines())
            output = re.search("successful", output).group()
            if output == "successful" or time.time() > timeout:
                return output

    def get_ue_TUN_name(self, imsi):
        self.execute_ssh_command(f"systemctl restart ueransim-ue-sim-{imsi}.service", sudo=True)
        timeout = time.time() + 60 * 1
        while True:
            stdout = self.execute_ssh_command(f"journalctl -u ueransim-ue-sim-{imsi}.service -b | grep TUN", sudo=True)
            output = stdout.readline()
            output = re.search("uesimtun[0-9]", output).group()
            if "uesimtun" in output or time.time() > timeout:
                return output

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
