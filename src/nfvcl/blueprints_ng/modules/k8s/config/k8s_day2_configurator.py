from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_core_models.resources import VmResourceAnsibleConfiguration


class VmK8sDay2Configurator(VmResourceAnsibleConfiguration):
    """
    This is the configurator for day0 of kubernetes nodes (master and workers)
    """
    _ansible_builder: AnsiblePlaybookBuilder = AnsiblePlaybookBuilder("K8s Master Day2Configurator")

    # _ in front of the name, so it is not serialized

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string.
        """

        return self._ansible_builder.build()
