import tempfile
from typing import Optional

import ansible_runner
from ansible_runner import Runner

from nfvcl_core.utils.log import create_logger
from nfvcl_providers.utils import create_ansible_inventory


def run_ansible_playbook(host: str, username: str, password: str, playbook: str, logger=create_logger("Ansible Configurator"), become_password: Optional[str] = None) -> (Runner, dict):
    tmp_playbook = tempfile.NamedTemporaryFile(mode="w")
    tmp_inventory = tempfile.NamedTemporaryFile(mode="w")
    tmp_private_data_dir = tempfile.TemporaryDirectory()

    # Write the inventory and playbook to files
    tmp_inventory.write(create_ansible_inventory(host, username, password, become_password=become_password))
    tmp_playbook.write(playbook)
    tmp_playbook.flush()
    tmp_inventory.flush()

    def my_status_handler(data, runner_config):
        logger.info(f"[ANSIBLE] Current status: {data['status']}")

    def my_event_handler(data):
        # TODO change logging type if error
        block = data["stdout"].strip()
        if len(block) > 0:
            lines = block.split("\n")
            for line in lines:
                logger.debug(f"[ANSIBLE] {line.strip()}")

    # Run the playbook, TODO better integration, error checking, logging, ...
    ansible_runner_result = ansible_runner.run(
        playbook=tmp_playbook.name,
        inventory=tmp_inventory.name,
        private_data_dir=tmp_private_data_dir.name,
        status_handler=my_status_handler,
        event_handler=my_event_handler,
        quiet=True
    )

    # Save the fact cache to a variable before deleting tmp_private_data_dir
    fact_cache = ansible_runner_result.get_fact_cache(host)

    # Close the tmp files, this will delete them
    tmp_playbook.close()
    tmp_inventory.close()
    tmp_private_data_dir.cleanup()

    return ansible_runner_result, fact_cache
