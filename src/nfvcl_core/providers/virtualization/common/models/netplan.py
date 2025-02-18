from typing import List

from pydantic import Field

from nfvcl_core.blueprints.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_core_models.resources import VmResourceAnsibleConfiguration
from nfvcl_core_models.base_model import NFVCLBaseModel


class NetplanNetMatch(NFVCLBaseModel):
    macaddress: str = Field()


class DhcpOverride(NFVCLBaseModel):
    # hostname: Optional[str] = Field()
    # route_metric: Optional[int] = Field(alias="route-metric")
    # send_hostname: Optional[bool] = Field(alias="send-hostname")
    # use_dns: Optional[bool] = Field(alias="use-dns")
    # use_domains: Optional[bool] = Field(alias="use-domains")
    # use_hostname: Optional[bool] = Field(alias="use-hostname")
    # use_mtu: Optional[bool] = Field(alias="use-mtu")
    # use_ntp: Optional[bool] = Field(alias="use-ntp")
    use_routes: bool = Field(default=False, alias="use-routes")


class NetplanNetConfig(NFVCLBaseModel):
    dhcp4: str = Field()
    dhcp4_overrides: DhcpOverride = Field(alias="dhcp4-overrides")
    set_name: str = Field(alias="set-name")
    match: NetplanNetMatch = Field()


class NetplanInterface(NFVCLBaseModel):
    nic_name: str = Field()
    mac_address: str = Field()


class VmAddNicNetplanConfigurator(VmResourceAnsibleConfiguration):
    """
    This configurator is used to add a nic to the netplan configuration of a VM and reload
    """
    nics: List[NetplanInterface] = Field(default_factory=list)

    def dump_playbook(self) -> str:
        ansible_playbook_builder = AnsiblePlaybookBuilder("Add nic to netplan")

        for nic in self.nics:
            netplan_config_to_add = NetplanNetConfig(dhcp4="true", set_name=nic.nic_name, match=NetplanNetMatch(macaddress=nic.mac_address), dhcp4_overrides=DhcpOverride())
            ansible_playbook_builder.add_shell_task(f"netplan set --origin-hint 50-cloud-init 'network.ethernets.{nic.nic_name}={netplan_config_to_add.model_dump_json(by_alias=True)}'")
        ansible_playbook_builder.add_shell_task("netplan apply")

        return ansible_playbook_builder.build()
