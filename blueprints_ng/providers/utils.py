import time
from typing import Optional, List

import paramiko


def create_ansible_inventory(host: str, username: str, password: str, become_password: Optional[str] = None):
    str_list: List[str] = [f"ansible_host='{host}'", f"ansible_user='{username}'", f"ansible_password='{password}'"]

    if become_password:
        str_list.append(f"ansible_become_pass='{become_password}'")

    return f"host {' '.join(str_list)}"


def wait_for_ssh_to_be_ready(host: str, port: int, user: str, passwd: str, timeout: int, retry_interval: float) -> bool:
    print(f"Starting SSH connection to {host}:{port} as user <{user}> and passwd <{passwd}>. Timeout is {timeout}, retry interval is {retry_interval}")
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    timeout_start = time.time()
    while time.time() < timeout_start + timeout:
        try:
            client.connect(host, port, username=user, password=passwd, allow_agent=False, look_for_keys=False)
            print('SSH transport is available!')
            client.close()
            return True
        except paramiko.ssh_exception.SSHException as e:
            # socket is open, but not SSH service responded
            print("socket is open, but not SSH service responded")
            print(e)
            time.sleep(retry_interval)
            continue

        except paramiko.ssh_exception.NoValidConnectionsError as e:
            print('SSH transport is not ready...')
            time.sleep(retry_interval)
            continue
    return False
