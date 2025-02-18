from typing import List, Optional, Dict

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel


class ProxmoxTicket(NFVCLBaseModel):
    ticket: Optional[str] = Field(default=None)
    csrfpreventiontoken: Optional[str] = Field(default=None)


class ProxmoxMac(NFVCLBaseModel):
    mac: str = Field()
    net_name: str = Field()
    hw_interface_name: str = Field()
    interface_name: str = Field()


class ProxmoxZone(NFVCLBaseModel):
    digest: str = Field()
    dhcp: Optional[str] = Field(default=None)
    dns: Optional[str] = Field(default=None)
    dnszone: Optional[str] = Field(default=None)
    ipam: Optional[str] = Field(default=None)
    mtu: Optional[int] = Field(default=None)
    nodes: Optional[str] = Field(default=None)
    pending: Optional[bool] = Field(default=None)
    reversedns: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    type: str = Field()
    zone: str = Field()


class ProxmoxZones(NFVCLBaseModel):
    data: List[ProxmoxZone] = Field(default_factory=list)


class ProxmoxInterface(NFVCLBaseModel):
    name: str = Field()
    mac_address: str = Field()


class ProxmoxNode(NFVCLBaseModel):
    node: str = Field()
    status: str = Field()
    cpu: Optional[float] = Field(default=None)
    level: Optional[str] = Field(default=None)
    maxcpu: Optional[int] = Field(default=None)
    maxmem: Optional[int] = Field(default=None)
    mem: Optional[int] = Field(default=None)
    ssl_fingerprint: Optional[str] = Field(default=None)
    uptime: Optional[int] = Field(default=None)


class ProxmoxNodes(NFVCLBaseModel):
    data: List[ProxmoxNode] = Field(default_factory=list)


class ProxmoxNetsDevice(NFVCLBaseModel):
    nets: Dict[str, List[str]] = Field(default_factory=dict)

    def add_net_device(self, vmid: str):
        interface_name = self.get_next_available_interface(vmid)
        if vmid not in self.nets.keys():
            self.nets[vmid] = []
        self.nets[vmid].append(interface_name)
        return interface_name

    def get_next_available_interface(self, vmid: str):
        if vmid in self.nets.keys():
            next_index = int(self.nets[vmid][-1].split('net')[1]) + 1
            return f"net{next_index}"
        else:
            return "net0"


class DhcpRangeItem(NFVCLBaseModel):
    end_address: str = Field(default=None, alias='end-address')
    start_address: str = Field(default=None, alias='start-address')


class Subnet(NFVCLBaseModel):
    dhcp_range: Optional[List[DhcpRangeItem]] = Field(default_factory=list, alias='dhcp-range')
    vnet: Optional[str] = Field(default=None)
    subnet: Optional[str] = Field(default=None)
    mask: Optional[str] = Field(default=None)
    type: Optional[str] = Field(default=None)
    gateway: Optional[str] = Field(default=None)
    id: Optional[str] = Field(default=None)
    cidr: str
    network: Optional[str] = Field(default=None)
    zone: str
    digest: Optional[str] = Field(default=None)


class Subnets(NFVCLBaseModel):
    data: List[Subnet] = Field(default_factory=list)
