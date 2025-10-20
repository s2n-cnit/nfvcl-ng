from typing import List, Optional, Dict

from pydantic import Field, ConfigDict

from nfvcl_core_models.base_model import NFVCLBaseModel


class ProxmoxBaseModel(NFVCLBaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Allow creating model object using the field name instead of the alias
        extra="allow",  # Allow extra fields in the model to account for Proxmox API changes and fields not yet defined in the model
        use_enum_values=True,  # Needed to be able to save the state to the mongo DB
        validate_default=True,
        validate_assignment=True
    )


class ProxmoxTicket(ProxmoxBaseModel):
    ticket: Optional[str] = Field(default=None)
    csrfpreventiontoken: Optional[str] = Field(default=None)


class ProxmoxMac(ProxmoxBaseModel):
    mac: str = Field()
    net_name: str = Field()
    hw_interface_name: str = Field()
    interface_name: str = Field()


class ProxmoxZone(ProxmoxBaseModel):
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


class ProxmoxZones(ProxmoxBaseModel):
    data: List[ProxmoxZone] = Field(default_factory=list)


class ProxmoxInterface(ProxmoxBaseModel):
    name: str = Field()
    mac_address: str = Field()


class ProxmoxNode(ProxmoxBaseModel):
    """
    {
    "status" : "online",
    "type" : "node",
    "disk" : 11806363648,
    "uptime" : 513931,
    "cpu" : 0.00346227316141356,
    "level" : "",
    "id" : "node/proxmoxnfvcl",
    "maxcpu" : 16,
    "maxdisk" : 100861726720,
    "mem" : 2506846208,
    "node" : "proxmoxnfvcl",
    "ssl_fingerprint" : "0A:49:6A:01:AF:52:ED:D7:2D:CC:B7:91:56:89:04:B6:A3:AA:6D:92:01:4B:ED:17:7C:E3:DF:3E:AC:FF:F4:09",
    "maxmem" : 67426443264
  } ]
    """
    status: str = Field()
    type: str = Field()
    disk: Optional[int] = Field(default=None)
    uptime: Optional[int] = Field(default=None)
    cpu: Optional[float] = Field(default=None)
    level: Optional[str] = Field(default=None)
    id: Optional[str] = Field(default=None)
    maxcpu: Optional[int] = Field(default=None)
    maxdisk: Optional[int] = Field(default=None)
    mem: Optional[int] = Field(default=None)
    node: str = Field()
    ssl_fingerprint: Optional[str] = Field(default=None)
    maxmem: Optional[int] = Field(default=None)


class ProxmoxNodes(ProxmoxBaseModel):
    data: List[ProxmoxNode] = Field(default_factory=list)


class ProxmoxNetsDevice(ProxmoxBaseModel):
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


class DhcpRangeItem(ProxmoxBaseModel):
    end_address: str = Field(default=None, alias='end-address')
    start_address: str = Field(default=None, alias='start-address')


class Vnet(ProxmoxBaseModel):
    alias: Optional[str] = Field(default=None)
    digest: Optional[str] = Field(default=None)
    isolate_ports: Optional[int] = Field(default=0, alias='isolate-ports')
    type: Optional[str] = Field(default=None)
    vlanaware: Optional[int] = Field(default=0)
    vnet: Optional[str] = Field(default=None)
    zone: Optional[str] = Field(default=None)


class Subnet(ProxmoxBaseModel):
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


class Subnets(ProxmoxBaseModel):
    data: List[Subnet] = Field(default_factory=list)

class Network(ProxmoxBaseModel):
    active: Optional[int] = Field(default=1)
    address: Optional[str] = Field(default=None)
    autostart: Optional[int] = Field(default=1)
    bridge_fd: Optional[str] = Field(default=None)
    bridge_ports: Optional[str] = Field(default=None)
    bridge_stp: Optional[str] = Field(default=None)
    bridge_vids: Optional[str] = Field(default=None)
    bridge_vlan_aware: Optional[int] = Field(default=1)
    cidr: Optional[str] = Field(default=None)
    families: Optional[List[str]] = Field(default_factory=list)
    gateway: Optional[str] = Field(default=None)
    iface: Optional[str] = Field(default=None)
    method: Optional[str] = Field(default=None)
    method6: Optional[str] = Field(default=None)
    netmask: Optional[str] = Field(default=None)
    priority: Optional[int] = Field(default=4)
    type: Optional[str] = Field(default=None)
