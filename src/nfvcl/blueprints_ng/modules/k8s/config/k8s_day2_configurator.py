from netaddr import IPNetwork

from nfvcl.blueprints_ng.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl.blueprints_ng.resources import VmResourceAnsibleConfiguration
from nfvcl.blueprints_ng.utils import rel_path
from nfvcl.utils.util import render_file_jinja2_to_str


class VmK8sDay2Configurator(VmResourceAnsibleConfiguration):
    """
    This is the configurator for day0 of kubernetes nodes (master and workers)
    """
    _ansible_builder: AnsiblePlaybookBuilder  # _ in front of the name, so it is not serialized

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string.
        """

        return self._ansible_builder.build()
