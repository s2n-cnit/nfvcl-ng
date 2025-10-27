from typing import List

from pydantic import Field

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder, AnsibleTaskDescription, AnsibleShellTask
from nfvcl_core_models.resources import VmResourceAnsibleConfiguration


class VmK8sDayNConfigurator(VmResourceAnsibleConfiguration):
    """
    This is the configurator for day0 of kubernetes nodes (master and workers)
    """
    task_list: List[AnsibleTaskDescription] = Field(default_factory=list)

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string.
        """
        ansible_builder = AnsiblePlaybookBuilder("Playbook K8S DayN Configurator")

        for task_description in self.task_list:
            ansible_builder.add_task_embedded(task_descr=task_description)
            ansible_builder.add_pause_task(30)
        self.task_list = []

        # Build the playbook and return it
        return ansible_builder.build()

    def delete_node(self, vm_name: str):
        command = f"kubectl drain {vm_name} --ignore-daemonsets --delete-emptydir-data"
        self.task_list.append(AnsibleTaskDescription.build(f"K8S node drain - {vm_name}", 'ansible.builtin.shell',AnsibleShellTask(cmd=command)))
        command = f"kubectl delete node {vm_name}"
        self.task_list.append(AnsibleTaskDescription.build(f"K8S node removal - {vm_name}", 'ansible.builtin.shell',AnsibleShellTask(cmd=command)))

