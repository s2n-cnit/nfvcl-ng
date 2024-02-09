from ipaddress import IPv4Address
from typing import List

from pydantic import Field

from models.base_model import NFVCLBaseModel


class VirtLinkDescr(NFVCLBaseModel):
    nsd_id: str = Field(default="")
    ns_vld_id: str
    vnfi_id: str
    vnfd_name: str = Field(default="")
    ip: str = Field(default="", description="Field containing an IP address or a list, divided by ;, of IP addresses")
    intf_name: str = Field(default="")
    external_cp_ref: str = Field(default="", alias="external-cp-ref")
    member_vnf_index_ref: str = Field(default="", alias="member-vnf-index-ref")
    intf_mac: str | None = None
    compute_node: str | None = None

    def get_ip(self) -> List[IPv4Address]:
        """
        Return a list of IP of the VLD (Every interface can have multiple IPs
        Returns:
            A list of IP, usually composed only by a single IP, but, when the interface has floating IPs (for example)
            more than one IP is returned.
        """
        return_list = []
        ip_list_str = self.ip.split(";")
        for ip in ip_list_str:
            return_list.append(IPv4Address(ip))

        return return_list

    def get_ip_str(self) -> List[str]:
        """
        Return a list of IP of the VLD (Every interface can have multiple IPs
        Returns:
            A list of IP, usually composed only by a single IP, but, when the interface has floating IPs (for example)
            more than one IP is returned.
        """
        ip_list_str = self.ip.split(";")

        return ip_list_str
