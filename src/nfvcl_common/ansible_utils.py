import logging
import tempfile
from typing import Optional, List

import ansible_runner
from ansible_runner import Runner

from nfvcl_common.utils.log import create_logger

def create_ansible_inventory(host: str, username: str, password: str, become_password: Optional[str] = None):
    str_list: List[str] = [f"ansible_host='{host}'", f"ansible_user='{username}'", f"ansible_password='{password}'"]

    if become_password:
        str_list.append(f"ansible_become_pass='{become_password}'")

    str_list.append("ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'")

    return f"{host} {' '.join(str_list)}"

def run_ansible_playbook(host: str, username: str, password: str, playbook: str, logger=create_logger("Ansible Configurator"), become_password: Optional[str] = None) -> (Runner, dict):
    """
    NEW APPROACH (Ansible >= 2.19.0): Uses event data to retrieve facts.

    This is the recommended approach, according to ansible-runner maintainers.
    Instead of using the fact cache, we iterate through events and extract
    the data we need from the appropriate event.
    """
    tmp_playbook = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
    tmp_inventory = tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False)
    tmp_private_data_dir = tempfile.TemporaryDirectory()

    collected_facts = {}

    def event_handler(event):
        """
        Process events to extract facts from set_fact tasks.
        This replaces the need to access the fact cache.
        """
        event_data = event.get('event_data', {})

        # Look for runner_on_ok events which contain task results
        if event.get('event') == 'runner_on_ok':
            task_name = event_data.get('task', '')
            res = event_data.get('res', {})

            # Check if this is a set_fact task with cacheable facts
            if 'ansible_facts' in res:
                ansible_facts = res['ansible_facts']
                logger.debug(f"[ANSIBLE] Found ansible_facts in event '{task_name}': {list(ansible_facts.keys())}")
                collected_facts.update(ansible_facts)

        block = event["stdout"].strip()
        if len(block) > 0:
            lines = block.split("\n")
            for line in lines:
                logger.debug(f"[ANSIBLE] {line.strip()}")

    try:
        # Write the inventory and playbook to files
        tmp_inventory.write(create_ansible_inventory(host, username, password, become_password=become_password))
        tmp_playbook.write(playbook)
        tmp_playbook.flush()
        tmp_inventory.flush()

        logger.info(f"Running playbook from {tmp_playbook.name}")
        logger.debug(f"Using inventory from {tmp_inventory.name}")
        logger.debug(f"Private data dir: {tmp_private_data_dir.name}")

        # Run the playbook with event handler
        ansible_runner_result = ansible_runner.run(
            playbook=tmp_playbook.name,
            inventory=tmp_inventory.name,
            private_data_dir=tmp_private_data_dir.name,
            event_handler=event_handler,
            quiet=True
        )

        logger.info(f"Playbook execution status: {ansible_runner_result.status}")
        logger.debug(f"Return code: {ansible_runner_result.rc}")
        logger.debug(f"Collected facts: {list(collected_facts.keys())}")

        return ansible_runner_result, collected_facts

    finally:
        # Clean up temp files
        tmp_playbook.close()
        tmp_inventory.close()
        tmp_private_data_dir.cleanup()
