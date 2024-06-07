from __future__ import annotations

from typing import List

from nfvcl.models.blueprint_ng.vyos.vyos_models import AnsibleVyOSInterface, AnsibleVyOSL3Interface
from nfvcl.blueprints_ng.ansible_builder import AnsiblePlaybookBuilder, AnsibleTaskDescription
from nfvcl.blueprints_ng.resources import VmResourceAnsibleConfiguration, VmResourceNetworkInterfaceAddress


class VmVyOSDay0Configurator(VmResourceAnsibleConfiguration):
    task_list: List[AnsibleTaskDescription] = []
    vars_to_be_collected: List[str] = []
    """
    This class is an example for an Ansible configurator for a VM

    The fields in this class will be saved to the DB and can be used to customize the configuration at runtime
    """

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string

        References:
            https://galaxy.ansible.com/ui/repo/published/vyos/vyos/docs/
        """

        # While not mandatory it is recommended to use AnsiblePlaybookBuilder to create the playbook
        ansible_builder = AnsiblePlaybookBuilder("Playbook ExampleVmUbuntuConfigurator")

        # Set the playbook variables (can be done anywhere in this method, but it needs to be before the build)
        ansible_builder.set_var("ansible_python_interpreter", "/usr/bin/python3")
        ansible_builder.set_var("ansible_network_os", "vyos")
        ansible_builder.set_var("ansible_connection", "network_cli")

        for task_description in self.task_list:
            ansible_builder.add_task_embedded(task_descr=task_description)
        self.task_list = []

        for var_to_collect in self.vars_to_be_collected:
            ansible_builder.add_gather_template_result_task(var_to_collect, "{{ " + var_to_collect + " }}")
        self.vars_to_be_collected = []

        # Build the playbook and return it
        return ansible_builder.build()

    def vyos_l1interfaces_collect_info(self):
        self.task_list.append(AnsibleTaskDescription.build("Collect L1 Info", 'vyos.vyos.vyos_interfaces', AnsibleVyOSInterface.retrieve_info(), register_name="l1info"))
        self.vars_to_be_collected.append("l1info")

    def initial_setup(self):
        config_task = AnsibleVyOSInterface.set_description_and_enable("eth0","Management Network", True)
        self.task_list.append(AnsibleTaskDescription.build("ETH0 set description", 'vyos.vyos.vyos_interfaces', task=config_task))

        for interface in self.vm_resource.get_additional_interfaces(): # Only int that are not the management one
            internal_int = interface.fixed
            self.__setup_data_int_task(internal_int)

        config_task = AnsibleVyOSInterface.set_loopback()
        self.task_list.append(AnsibleTaskDescription.build("Loopback set description", 'vyos.vyos.vyos_interfaces', task=config_task))
        data_config_task = AnsibleVyOSL3Interface.set_loopback()
        self.task_list.append(AnsibleTaskDescription.build(f"Loopback set IP 10.200.200.200/32", 'vyos.vyos.vyos_l3_interfaces', task=data_config_task))

    def __setup_data_int_task(self, interface: VmResourceNetworkInterfaceAddress):
        """
        """
        config_task = AnsibleVyOSInterface.set_description_mtu_and_enable(interface.interface_name, f"Data int - net {interface.cidr}", True)
        self.task_list.append(AnsibleTaskDescription.build(f"{interface.interface_name} set description", 'vyos.vyos.vyos_interfaces', task=config_task))
        data_config_task = AnsibleVyOSL3Interface.set_address(interface.interface_name, interface.get_ip_prefix())
        self.task_list.append(AnsibleTaskDescription.build(f"{interface.interface_name} set IP", 'vyos.vyos.vyos_l3_interfaces', task=data_config_task))
