import paramiko


class SSH:
    def __init__(self, ip, user=None, passwd=None):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(ip,
                         port=22, username="ubuntu" if user is None else user,
                         password="ubuntu" if passwd is None else passwd, timeout=3)

    def get_file_content(self, path: str):
        _, stdout, _ = self.ssh.exec_command(f"cat {path}")
        stdout = ' '.join(stdout.readlines())
        return stdout

    def close_connection(self):
        self.ssh.close()
