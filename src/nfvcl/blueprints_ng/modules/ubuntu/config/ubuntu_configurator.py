from typing import List

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_core_models.resources import VmResourceAnsibleConfiguration
from nfvcl_models.blueprint_ng.ubuntu.ubuntu_rest_models import UbuntuAptModel


class VmUbuntuConfigurator(VmResourceAnsibleConfiguration):
    """
    This is the configurator for day0 of kubernetes nodes (master and workers)
    """
    _ansible_builder: AnsiblePlaybookBuilder = AnsiblePlaybookBuilder("Ubuntu Day0 Configurator") # _ in front of the name, so it is not serialized !!!

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string.
        """
        return self._ansible_builder.build()

    def install_apt_packages(self, package_list: List[UbuntuAptModel]) -> None:
        """
        Install the given packages using apt
        """
        self._ansible_builder = AnsiblePlaybookBuilder("Ubuntu Day0 Configurator") # Reset the playbook

        update_cache = True
        for index, package in enumerate(package_list):
            if getattr(package, 'version', None):
                self._ansible_builder.add_apt_install_task(package.package, package_version=package.version, update_cache=update_cache)
            else:
                self._ansible_builder.add_apt_install_task(package.package, update_cache=update_cache)
            update_cache = False # Only the first iteration will update the cache
