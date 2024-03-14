from __future__ import annotations

from typing import List

from pydantic import Field

from blueprints_ng.ansible_builder import AnsibleTask


class AnsibleVyOSConfigTask(AnsibleTask):
    lines: List[str] = Field(default=[])
    save: str = Field(default='yes')

class AnsibleVyOSInterface(AnsibleTask):
    config: List[dict] = Field(default=[])
    state: str = Field(default='gathered')

    @classmethod
    def retrieve_info(cls):
        """
        Create a task to retrieve info about interfaces.

        Returns:
            A task to retrieve info about interfaces.
        """
        return AnsibleVyOSInterface()

    @classmethod
    def set_description_and_enable(cls, name: str, description: str, enable: bool):
        """
        Set description and enable/disable interface
        Args:
            name: Interface name
            description: Description to be set
            enable: if enable or not the interface

        Returns:
            Task that will set up name and enable/disable the desired interface.
        """
        configuration = {"name":name,"description":description,"enabled":"true" if enable else "false"}
        return AnsibleVyOSInterface(config=[configuration], state="merged")

    @classmethod
    def set_description_mtu_and_enable(cls, name: str, description: str, enable: bool):
        """
        Set description mtu and enable/disable interface
        Args:
            name: Interface name
            description: Description to be set
            enable: if enable or not the interface

        Returns:
            Task that will set up name and enable/disable the desired interface.
        """
        configuration = {"name": name, "description": description, "mtu": 1450, "enabled":"true" if enable else "false"}
        return AnsibleVyOSInterface(config=[configuration], state="merged")

    @classmethod
    def set_loopback(cls):
        """
        Setup loopback interface

        Returns:
            Task that will set up name and enable/disable the desired interface.
        """
        configuration = {"name": "lo", "description": "Loopback interface", "enabled":"true"}
        return AnsibleVyOSInterface(config=[configuration], state="merged")


class AnsibleVyOSL3Interface(AnsibleTask):
    config: List[dict] = Field(default=[])
    state: str = Field(default='gathered')

    @classmethod
    def retrieve_info(cls):
        """
        Create a task to retrieve info about L3 interfaces.
        Args:
            register_name: The name to be given at the variable containing the desired information

        Returns:
            A task to retrieve info about interfaces.
        """
        return AnsibleVyOSL3Interface()

    @classmethod
    def set_dhcp(cls, interface_name: str):
        """

        Args:
            interface_name: Interface name

        Returns:
            Task that will set up
        """
        configuration = {"name":interface_name, "ipv4": {"address":"dhcp"}}
        return AnsibleVyOSL3Interface(config=[configuration], state="merged")

    @classmethod
    def set_address(cls, interface_name: str, ipv4_and_mask: str):
        """

        Args:
            interface_name: Interface name
            ipv4_and_mask: IPV4 address in 192.3.3.1/23 format

        Returns:
            Task that w
        """
        configuration = {"name":interface_name, "ipv4": [{"address":ipv4_and_mask}]}
        return AnsibleVyOSL3Interface(config=[configuration], state="merged")

    @classmethod
    def set_loopback(cls):
        """
        Set

        Returns:
            Task that will set up
        """
        configuration = {"name":"lo", "ipv4": [{"address":"10.200.200.200/32"}]}
        return AnsibleVyOSL3Interface(config=[configuration], state="merged")

################################# EXCEPTIONS ########################################


class VyOSNATRuleAlreadyPresent(Exception):
    pass

class VyOSNATRuleNotFound(Exception):
    pass
