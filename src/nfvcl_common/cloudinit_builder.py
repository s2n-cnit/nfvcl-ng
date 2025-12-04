import hashlib
import io
from typing import List, Optional, Dict

from pycdlib import PyCdlib
from pydantic import Field, field_validator

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.blue_utils import get_yaml_parser


class CloudInitChpasswd(NFVCLBaseModel):
    list: List[str] = Field(default_factory=list)
    expire: bool = Field(default=False)


class CloudInit(NFVCLBaseModel):
    hostname: Optional[str] = Field(default=None)
    fqdn: Optional[str] = Field(default=None)
    manage_etc_hosts: bool = Field(default=True)
    chpasswd: CloudInitChpasswd = Field(default=CloudInitChpasswd())
    disable_root: bool = Field(default=False)
    ssh_pwauth: bool = Field(default=True)
    ssh_authorized_keys: Optional[List[str]] = Field(default=None)
    packages: Optional[List[str]] = Field(default=None)
    runcmd: Optional[List[str]] = Field(default=None)

    def add_user(self, username: str, password: str):
        self.chpasswd.list.append(f'{username}:{password}')
        if username == "root":
            self.runcmd.append("sed -i'.orig' -e's/PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config")
            self.runcmd.append("sed -i'.orig' -e's/#PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config")
            self.runcmd.append("service sshd restart")

    def build_cloud_config(self) -> str:
        return f"#cloud-config\n{get_yaml_parser().dump(self.model_dump(exclude_none=True))}"

    @field_validator("hostname", "fqdn")
    def hostname_validator(cls, v: Optional[str]):
        if v is None:
            return None
        return v.lower().replace(" ", "-").replace("_", "-")


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
#     type___: str = Field(default="dhcp") # added ___ because otherwise this being a comment break mypy
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
    network: CloudInitNetwork = Field(default_factory=CloudInitNetwork)

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


def create_cloud_init_iso(meta_data="", user_data="", vendor_data="", network_config=""):
    iso = PyCdlib()
    iso.new(interchange_level=4, vol_ident='cidata', joliet=3)

    def add_cloudinit_file(content, filename):
        if content:
            iso.add_fp(
                io.BytesIO(content.encode("utf-8")),
                length=len(content.encode("utf-8")),
                joliet_path=f'/{filename}'
            )

    add_cloudinit_file(meta_data, "meta-data")
    add_cloudinit_file(user_data, "user-data")
    add_cloudinit_file(vendor_data, "vendor-data")
    add_cloudinit_file(network_config, "network-config")

    buf = io.BytesIO()
    iso.write_fp(buf)
    iso.close()

    iso_bytes = buf.getvalue()
    sha256sum = hashlib.sha256(iso_bytes).hexdigest()

    return io.BytesIO(iso_bytes), sha256sum
