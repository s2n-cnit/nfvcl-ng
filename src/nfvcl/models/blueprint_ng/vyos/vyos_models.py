from __future__ import annotations
from typing import List
from typing import Optional
from pydantic import BaseModel, Field
from nfvcl.blueprints_ng.ansible_builder import AnsibleTask


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
        configuration = {"name": name, "description": description, "enabled": "true" if enable else "false"}
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
        configuration = {"name": name, "description": description, "mtu": 1450, "enabled": "true" if enable else "false"}
        return AnsibleVyOSInterface(config=[configuration], state="merged")

    @classmethod
    def set_loopback(cls):
        """
        Setup loopback interface

        Returns:
            Task that will set up name and enable/disable the desired interface.
        """
        configuration = {"name": "lo", "description": "Loopback interface", "enabled": "true"}
        return AnsibleVyOSInterface(config=[configuration], state="merged")


class AnsibleVyOSL3Interface(AnsibleTask):
    config: List[dict] = Field(default=[])
    state: str = Field(default='gathered')

    @classmethod
    def retrieve_info(cls):
        """
        Create a task to retrieve info about L3 interfaces.

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
        configuration = {"name": interface_name, "ipv4": {"address": "dhcp"}}
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
        configuration = {"name": interface_name, "ipv4": [{"address": ipv4_and_mask}]}
        return AnsibleVyOSL3Interface(config=[configuration], state="merged")

    @classmethod
    def set_loopback(cls):
        """
        Set

        Returns:
            Task that will set up
        """
        configuration = {"name": "lo", "ipv4": [{"address": "10.200.200.200/32"}]}
        return AnsibleVyOSL3Interface(config=[configuration], state="merged")


class VyOSSourceNATRule(BaseModel):
    """
    Source NAT is a translation of the source IP address of packets
     - exiting from an interface
     - being part of a determined IP range (source IP)
    into the desired ip
    """
    outbound_network: str = Field(title="The network to which the source IP translation is applied. Example 10.0.0.0/16")  # TODO remove not used by SNAT RULE
    outbound_interface: Optional[str] = Field(default=None)
    source_address: str = Field(title="The source IP or ip range to witch the rule is applied. Example 10.170.2.0/24")
    virtual_ip: str = Field(default="masquerade", title="The desired new IP of packets exiting the interface. This value"
                                                        "can be set to 'masquerade' or to a valid IP/32 (10.170.2.66)")
    rule_number: int = Field(default=1, title="The rule number. It already present the rule is overwritten on the router.")
    description: str = Field(title="Description to assign at the rule")


class VyOSDestNATRule(BaseModel):
    """
    A Destination NAT is a translation of the destination IP (which fall in a desired range) coming from a specified
    interface (can be retrived by the network) to a new IP address.
    """
    inbound_network: str = Field(title="The network from which to listen. Example 10.0.0.0/16")
    inbound_interface: Optional[str] = Field(default=None)
    virtual_ip: str = Field(title="The virtual IP represent the target IP or the IP range to convert into the "
                                  "real_destination_ip. Example 7.7.7.7")
    real_destination_ip: str = Field(title="The real destination. Example 192.168.0.45")
    rule_number: int = Field(default=1, title="The rule number. It already present the rule is overwritten on the router.")
    description: str = Field(default="", title="Description to assign at the rule")


class VyOS1to1NATRule(BaseModel):
    """
    A 1 to 1 NAT rule is a combination of source and destination NAT.
    """
    inbound_network: str = Field(title="From which network the destination translation is done. Example 10.168.0.0/16")
    virtual_ip: str = Field(title="The virtual ip (not assigned to any interface of the router) to be translated"
                                  "the real destination ip. Example 7.7.7.7")
    real_destination_ip: str = Field(title="The real destination behind the virtual IP. Example 192.168.0.45")
    source_address: str = Field(title="The IP address to convert into the virtual IP (source NAT). This field should correspond to real destination IP to realize 1 to 1 NAT. Example 192.168.0.45")
    outbound_network: str = Field(title="The network to send the packet coming from source_address IP. This field should correspond to inbound_network for 1 to 1 NAT. Example 10.168.0.0/16")
    rule_number: int = Field(default=1, title="The rule number. It already present the rule is overwritten on the router.")
    description: str = Field(default="", title="Description to assign at the rule")
    outbound_interface: Optional[str]
    inbound_interface: Optional[str]


# --------------------------- EXCEPTIONS ------------------------------------------------
class VyOSNATRuleAlreadyPresent(Exception):
    pass


class VyOSNATRuleNotFound(Exception):
    pass


class VyOSNetworkNotConnectedToVM(Exception):
    pass


class VyOSInterfaceNotExisting(Exception):
    pass
