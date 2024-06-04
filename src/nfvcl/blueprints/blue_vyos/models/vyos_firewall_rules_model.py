from typing import Optional

from pydantic import BaseModel, Field


class VyOSFirewallRule(BaseModel):
    """
    A firewall is a network security device or software that monitors and controls incoming and outgoing network
    traffic based on predetermined security rules

    """
    interface_group_name: Optional[str] = Field(default=None)
    interface: Optional[str] = Field(default=None)
    port_group_name: Optional[str] = Field(default=None)
    port_number: Optional[int] = Field(default=None)
    address_group_name: Optional[str] = Field(default=None)
    address: Optional[str] = Field(default=None)
    network_group_name: Optional[str] = Field(default=None)
    network: Optional[str] = Field(default=None)

class VyOSFirewallRuleSecond(BaseModel):
    """
    A firewall is a network security device or software that monitors and controls incoming and outgoing network
    traffic based on predetermined security rules

    """
    firewallname: str = Field(title="Network Name")
    defaultaction: Optional[str] = Field(default='drop', title="Default Action of the Firewall")
    en_ping: Optional[str] = Field(default='enable',
                         title="all ping enable/disable. If enable is set, VyOS will answer every ICMP echo request"
                               " addressed to itself, but that will only happen if no other rule is applied dropping "
                               "or rejecting local echo requests")
    rule_number: Optional[int] = Field(default=None)
    action: Optional[str] = Field(default=None)
    protocol: Optional[str] = Field(title="protocol (tcp/udp, all, others)")
    var: Optional[str] = Field(title="destination/source")
    port: Optional[int] = Field(default=None)
    dest_address: Optional[str] = Field(default=None)
    port_group_name: Optional[str] = Field(default=None)
    address_group_name: Optional[str] = Field(default=None)
    network_group_name: Optional[str] = Field(default=None)
    interface: Optional[str] = Field(default=None)
    variable: Optional[str] = Field(default=None, title="local, in or out")
    interface_group_name: Optional[str] = Field(default=None)





