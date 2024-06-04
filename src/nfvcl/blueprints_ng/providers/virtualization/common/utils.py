import time

import paramiko

from nfvcl.utils.log import create_logger

logger = create_logger('Providers_Utils')

def wait_for_ssh_to_be_ready(host: str, port: int, user: str, passwd: str, timeout: int, retry_interval: float) -> bool:
    logger.debug(f"Starting SSH connection to {host}:{port} as user <{user}> and passwd <{passwd}>. Timeout is {timeout}, retry interval is {retry_interval}")
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    timeout_start = time.time()
    while time.time() < timeout_start + timeout:
        try:
            client.connect(host, port, username=user, password=passwd, allow_agent=False, look_for_keys=False)
            logger.debug('SSH transport is available!')
            client.close()
            return True
        except paramiko.ssh_exception.SSHException as e:
            # socket is open, but not SSH service responded
            logger.debug(f"Socket is open, but not SSH service responded: {e}")
            time.sleep(retry_interval)
            continue

        except paramiko.ssh_exception.NoValidConnectionsError as e:
            logger.debug('SSH transport is not ready...')
            time.sleep(retry_interval)
            continue
    return False
