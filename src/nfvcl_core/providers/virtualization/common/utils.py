import time
from pathlib import Path
from typing import Optional

import paramiko
import verboselogs

from nfvcl_core.providers.configurators.ansible_utils import run_ansible_playbook
from nfvcl_core.providers.virtualization.virtualization_provider_interface import \
    VirtualizationProviderException
from nfvcl_core.models.resources import VmResourceAnsibleConfiguration
from nfvcl_core.utils.file_utils import create_tmp_folder
from nfvcl_core.utils.log import create_logger

logger_pu = create_logger('Providers_Utils')


class VirtualizationConfiguratorException(VirtualizationProviderException):
    pass


def wait_for_ssh_to_be_ready(host: str, port: int, user: str, passwd: str, timeout: int, retry_interval: float, logger_override: Optional[verboselogs.VerboseLogger] = None) -> bool:
    if logger_override:
        logger = logger_override
    else:
        logger = logger_pu

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


def configure_machine_ansible(ip: str, username: str, password: str, playbook: str, logger_override: Optional[verboselogs.VerboseLogger] = None, become_password: Optional[str] = None) -> dict:
    if logger_override:
        logger = logger_override
    else:
        logger = logger_pu

    ansible_runner_result, fact_cache = run_ansible_playbook(
        ip,
        username,
        password,
        playbook,
        logger,
        become_password=become_password
    )

    if ansible_runner_result.status == "failed":
        raise VirtualizationConfiguratorException("Error running ansible configurator")

    return fact_cache

def configure_vm_ansible(vm_resource_configuration: VmResourceAnsibleConfiguration, blueprint_id: str, logger_override: Optional[verboselogs.VerboseLogger] = None) -> dict:
    if logger_override:
        logger = logger_override
    else:
        logger = logger_pu

    nfvcl_tmp_dir = create_tmp_folder("nfvcl/playbook")  # Path("/tmp/nfvcl/playbook")

    playbook_str = vm_resource_configuration.dump_playbook()

    with open(Path(nfvcl_tmp_dir, f"{blueprint_id}_{vm_resource_configuration.vm_resource.name}.yml"), "w+") as f:
        f.write(playbook_str)

    # Wait for SSH to be ready, this is needed because sometimes cloudinit is still not finished and the server doesn't allow password connections
    wait_for_ssh_to_be_ready(
        vm_resource_configuration.vm_resource.access_ip,
        22,
        vm_resource_configuration.vm_resource.username,
        vm_resource_configuration.vm_resource.password,
        300,
        5,
        logger_override=logger_override
    )

    fact_cache = configure_machine_ansible(
        vm_resource_configuration.vm_resource.access_ip,
        vm_resource_configuration.vm_resource.username,
        vm_resource_configuration.vm_resource.password,
        playbook_str,
        logger
    )

    return fact_cache
