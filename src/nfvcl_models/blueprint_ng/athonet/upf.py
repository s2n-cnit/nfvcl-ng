

import ipaddress
from typing import List, Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel


################### PDU INFO ####################

class DnnVrf(NFVCLBaseModel):
    dnn: str
    vrf: str
    cidr: str
    dns: str


class DnnVrfMapping(NFVCLBaseModel):
    dnns: List[DnnVrf]


#################### APPLICATION CONFIG ####################

class ApplicationConfig(NFVCLBaseModel):
    heartbeat_interval_ms: int
    max_retransmissions: int
    retransmission_timeout_ms: int


class PfcpTransportConfig(NFVCLBaseModel):
    type: str
    tos: int
    local_addr: str
    dev: str


class PfcpTransport(NFVCLBaseModel):
    name: str
    transport_config: PfcpTransportConfig


class Pfcp(NFVCLBaseModel):
    config: ApplicationConfig
    transports: List[PfcpTransport]


class Logs(NFVCLBaseModel):
    level: str


class VnetDevice(NFVCLBaseModel):
    dev: str


class DataType(NFVCLBaseModel):
    ip: bool
    gtp: bool
    eth: bool


class UplaneDevice(NFVCLBaseModel):
    dev: str
    data_type: DataType


class VrfLink(NFVCLBaseModel):
    interface: str
    direction: str
    vrf: str
    network_instance: str
    apn_dnn: Optional[str] = None


class DataPlane(NFVCLBaseModel):
    routes: List
    vnet_devices: List[VnetDevice]
    uplane_devices: List[UplaneDevice]
    vrf_links: List[VrfLink]


class Pool(NFVCLBaseModel):
    max: str
    min: str
    name: str
    dnn: str
    network_instance: str


class IpPools(NFVCLBaseModel):
    pools: List[Pool]
    ue_ip_routes: bool


class Tag(NFVCLBaseModel):
    access: Optional[bool] = None
    cp_function: Optional[bool] = None
    core: Optional[bool] = None


class GtpuTransportConfig(NFVCLBaseModel):
    type: str
    local_addr: str
    dev: str


class GtpuTransport(NFVCLBaseModel):
    name: str
    tag: Tag
    transport_config: GtpuTransportConfig


class Gtpu(NFVCLBaseModel):
    transports: List[GtpuTransport]


class License(NFVCLBaseModel):
    license_server: str
    license_id: str


class AthonetApplicationUpfConfig(NFVCLBaseModel):
    version: Optional[str] = None
    pfcp: Optional[Pfcp] = None
    logs: Optional[Logs] = None
    api_version: Optional[str] = None
    data_plane: Optional[DataPlane] = None
    ip_pools: Optional[IpPools] = None
    gtpu: Optional[Gtpu] = None
    license: Optional[License] = None

    def clear_config(self, dnns: List[DnnVrf]):
        """
        Clear all ip pools and vrf from upf config
        Args:
            dnns: list of all available dnn with associated cidr and dns

        """
        self.ip_pools.pools.clear()
        for dnn in dnns:
            for vrf in self.data_plane.vrf_links.copy():
                if vrf.vrf == dnn.vrf:
                    self.data_plane.vrf_links.remove(vrf)

    def configure(self, dnn_vrf: List[DnnVrf], config: UPFBlueCreateModel):
        """
        Configure UPF according to upf payload model
        Args:
            dnn_vrf: list of all available dnn with associated cidr and dns
            config: upf model

        """
        self.clear_config(dnn_vrf)
        for _slice in config.slices:
            for dnn in _slice.dnn_list:
                for supported_dnn in dnn_vrf:
                    if supported_dnn.cidr == dnn.cidr:
                        ingress = VrfLink(interface="core", direction="ingress", vrf=supported_dnn.vrf, network_instance=f"NI_{supported_dnn.vrf}", apn_dnn=dnn.dnn)
                        egress = VrfLink(interface="core", direction="egress", vrf=supported_dnn.vrf, network_instance=f"NI_{supported_dnn.vrf}", apn_dnn=dnn.dnn)
                        self.data_plane.vrf_links.append(ingress)
                        self.data_plane.vrf_links.append(egress)
                        ip = ipaddress.ip_network(supported_dnn.cidr)
                        pool = Pool(max=ip[-2].exploded, min=ip[1].exploded, name=f"{dnn.dnn}_pubblic_pool_v4_0", dnn=dnn.dnn, network_instance=f"NI_{supported_dnn.vrf}")
                        self.ip_pools.pools.append(pool)


#################### NETWORK CONFIG ####################

class InterfaceVrf(NFVCLBaseModel):
    table: int


class Vlan(NFVCLBaseModel):
    id: int


class InterfaceLink(NFVCLBaseModel):
    generic_receive_offload: bool
    generic_segmentation_offload: bool
    large_receive_offload: bool
    tcp_segmentation_offload: bool
    tcp6_segmentation_offload: bool
    receive_checksum_offload: bool
    transmit_checksum_offload: bool
    rx_flow_control: bool
    tx_flow_control: bool


class InterfaceConfig(NFVCLBaseModel):
    vrf: Optional[InterfaceVrf] = None
    vlan: Optional[Vlan] = None
    link: Optional[InterfaceLink] = None


class Interface(NFVCLBaseModel):
    kind: str
    name: str
    config: Optional[InterfaceConfig] = None


class Addres(NFVCLBaseModel):
    address: str


class Match(NFVCLBaseModel):
    name: List[str]


class RouteItem(NFVCLBaseModel):
    destination: str
    gateway: Optional[str] = None
    scope: Optional[str] = None


class NetworkLink(NFVCLBaseModel):
    mtu_bytes: str
    unmanaged: bool


class NetworkConfigNetwork(NFVCLBaseModel):
    vrf: Optional[str] = None
    vlan: Optional[List[str]] = None
    proxy_arp: Optional[bool] = None
    configure_without_carrier: Optional[bool] = None


class NetworkConfig(NFVCLBaseModel):
    address: Optional[List[Addres]] = None
    match: Match
    route: Optional[List[RouteItem]] = None
    link: Optional[NetworkLink] = None
    network: Optional[NetworkConfigNetwork] = None
    routing_policy_rule: Optional[List] = None


class Network(NFVCLBaseModel):
    name: str
    config: NetworkConfig


class Time(NFVCLBaseModel):
    ntp: List[str]


class Timesyncd(NFVCLBaseModel):
    time: Time


class Hostnamed(NFVCLBaseModel):
    hostname: str


class Filter(NFVCLBaseModel):
    name: str
    body: str


class Pattern(NFVCLBaseModel):
    exclude: bool
    match: str


class IdleTxInterval(NFVCLBaseModel):
    time: int
    unit: str


class MinRxInterval(NFVCLBaseModel):
    time: int
    unit: str


class MinTxInterval(NFVCLBaseModel):
    time: int
    unit: str


class OptionsInterface(NFVCLBaseModel):
    patterns: List[Pattern]
    idle_tx_interval: Optional[IdleTxInterval] = None
    min_rx_interval: Optional[MinRxInterval] = None
    min_tx_interval: Optional[MinTxInterval] = None
    multiplier: Optional[int] = None


class Import(NFVCLBaseModel):
    filter: str


class Export(NFVCLBaseModel):
    expr: Optional[str] = None
    filter: str
    name: Optional[str] = None


class Options1(NFVCLBaseModel):
    import_: Import = Field(..., alias='import')
    table: str
    export: Optional[Export] = None


class Channel(NFVCLBaseModel):
    kind: str
    options: Options1


class MergePaths(NFVCLBaseModel):
    enable: bool


class Local(NFVCLBaseModel):
    as_: int = Field(..., alias='as')


class Remote(NFVCLBaseModel):
    ip: str
    kind: str


class Neighbor(NFVCLBaseModel):
    as_: int = Field(..., alias='as')
    remote: Remote


class Session(NFVCLBaseModel):
    kind: str


class Options(NFVCLBaseModel):
    interfaces: Optional[List[OptionsInterface]] = None
    scan_time: Optional[int] = None
    channels: Optional[List[Channel]] = None
    kernel_table: Optional[int] = None
    learn: Optional[bool] = None
    merge_paths: Optional[MergePaths] = None
    persist: Optional[bool] = None
    local: Optional[Local] = None
    neighbor: Optional[Neighbor] = None
    session: Optional[Session] = None


class ProtocolVrf(NFVCLBaseModel):
    kind: str
    vrf: str


class Protocol(NFVCLBaseModel):
    kind: str
    name: str
    options: Options
    vrf: Optional[ProtocolVrf] = None


class Table(NFVCLBaseModel):
    kind: str
    name: str


class Bird(NFVCLBaseModel):
    enable: bool
    filters: List[Filter]
    protocols: List[Protocol]
    tables: List[Table]


class MssClampingRule(NFVCLBaseModel):
    kind: str
    interface: str
    mss: int


class Firewall(NFVCLBaseModel):
    mss_clamping_rules: List[MssClampingRule]


class AthonetNetworkUpfConfig(NFVCLBaseModel):
    logs: Optional[Logs] = None
    interfaces: Optional[List[Interface]] = None
    networks: Optional[List[Network]] = None
    timesyncd: Optional[Timesyncd] = None
    hostnamed: Optional[Hostnamed] = None
    bird: Optional[Bird] = None
    firewall: Optional[Firewall] = None
