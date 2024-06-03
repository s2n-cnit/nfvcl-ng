from enum import Enum
from typing import List, Optional, Dict

from pydantic import Field

from blueprints_ng.utils import get_yaml_parser
from models.base_model import NFVCLBaseModel


class CloudInitChpasswd(NFVCLBaseModel):
    expire: bool = Field(default=False)


class CloudInit(NFVCLBaseModel):
    manage_etc_hosts: bool = Field(default=True)
    password: str = Field()
    chpasswd: CloudInitChpasswd = Field(default=CloudInitChpasswd())
    ssh_pwauth: bool = Field(default=True)
    ssh_authorized_keys: Optional[List[str]] = Field(default=None)
    packages: Optional[List[str]] = Field(default=None)
    runcmd: Optional[List[str]] = Field(default=None)

    def build_cloud_config(self) -> str:
        return f"#cloud-config\n{get_yaml_parser().dump(self.model_dump(exclude_none=True))}"


class CloudInitDhcpOverride(NFVCLBaseModel):
    # hostname: Optional[str] = Field()
    # route_metric: Optional[int] = Field(alias="route-metric")
    # send_hostname: Optional[bool] = Field(alias="send-hostname")
    # use_dns: Optional[bool] = Field(alias="use-dns")
    # use_domains: Optional[bool] = Field(alias="use-domains")
    # use_hostname: Optional[bool] = Field(alias="use-hostname")
    # use_mtu: Optional[bool] = Field(alias="use-mtu")
    # use_ntp: Optional[bool] = Field(alias="use-ntp")
    use_routes: bool = Field(alias="use-routes", default=False)


# class CloudInitSubnet(NFVCLBaseModel):
#     type: str = Field(default="dhcp")
#     dhcp4_overrides: Optional[CloudInitDhcpOverride] = Field(default=None, alias='dhcp4-overrides')


class MatchType(NFVCLBaseModel):
    macaddress: str = Field()


class InterfaceCloudInit(NFVCLBaseModel):
    dhcp4: bool = Field(default=True)
    dhcp4_overrides: Optional[CloudInitDhcpOverride] = Field(default=None, alias="dhcp4-overrides")
    match: MatchType = Field()
    set_name: str = Field(alias="set-name")


class CloudInitNetwork(NFVCLBaseModel):
    version: int = Field(default=2)
    ethernets: Dict[str, InterfaceCloudInit] = Field(default_factory=dict)
    # bridges: Optional[List[InterfaceCloudInit]] = Field(default_factory=list) #TODO Implement if needed
    # vlans: Optional[List[InterfaceCloudInit]] = Field(default_factory=list) #TODO Implement if needed
    # bonds: Optional[List[InterfaceCloudInit]] = Field(default_factory=list) #TODO Implement if needed


class CloudInitNetworkRoot(NFVCLBaseModel):
    network: CloudInitNetwork = Field(default=CloudInitNetwork())

    def add_device(self, iface: str, macaddress: str, override=False):
        tmp = InterfaceCloudInit(
            match=MatchType(macaddress=macaddress),
            set_name=iface
        )
        if override:
            tmp.dhcp4_overrides = CloudInitDhcpOverride()
        self.network.ethernets[iface] = tmp

    def build_cloud_config(self) -> str:
        return get_yaml_parser().dump(self.model_dump(exclude_none=True, by_alias=True))
