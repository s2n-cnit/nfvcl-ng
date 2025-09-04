from typing import List, Optional

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.network.network_models import MultusInterface


class Prometheus(NFVCLBaseModel):
    port: int


class Hugepage(NFVCLBaseModel):
    enabled: Optional[bool] = Field(default=False)


class Sriov(NFVCLBaseModel):
    enabled: Optional[bool] = Field(default=False)


class Enb(NFVCLBaseModel):
    subnet: str


class UpfInterface(NFVCLBaseModel):
    resource_name: str = Field(default="intel.com/intel_sriov_vfio", alias='resourceName')
    gateway: Optional[str] = Field(default=None)
    ip: str
    iface: str
    mac: Optional[str] = Field(default=None)

    def set_multus(self, multus_interface: MultusInterface, gateway_ip=None, mac=None):
        self.gateway = gateway_ip
        self.ip = f"{multus_interface.ip_address.exploded}/{multus_interface.prefixlen}"
        self.iface = multus_interface.host_interface
        self.mac = mac


class TableSizes(NFVCLBaseModel):
    pdr_lookup: int = Field(default=50000, alias='pdrLookup')
    app_qer_lookup: int = Field(default=200000, alias='appQERLookup')
    session_qer_lookup: int = Field(default=100000, alias='sessionQERLookup')
    far_lookup: int = Field(default=150000, alias='farLookup')


class UpfJsoncInterface(NFVCLBaseModel):
    ifname: str


class Cpiface(NFVCLBaseModel):
    dnn: str
    hostname: str
    http_port: str
    enable_ue_ip_alloc: Optional[bool] = Field(default=False)
    ue_ip_pool: Optional[str] = Field(default=None)


class SliceRateLimitConfig(NFVCLBaseModel):
    n6_bps: Optional[int] = Field(default=500000000)
    n6_burst_bytes: Optional[int] = Field(default=625000)
    n3_bps: Optional[int] = Field(default=500000000)
    n3_burst_bytes: Optional[int] = Field(default=625000)


class QciQosConfigItem(NFVCLBaseModel):
    qci: Optional[int] = Field(default=0)
    cbs: Optional[int] = Field(default=50000)
    ebs: Optional[int] = Field(default=50000)
    pbs: Optional[int] = Field(default=50000)
    burst_duration_ms: Optional[int] = Field(default=10)
    priority: Optional[int] = Field(default=7)

class P4rtciface(NFVCLBaseModel):
    access_ip: Optional[str] = Field(default="172.17.0.1/32")
    p4rtc_server: Optional[str] = Field(default="onos")
    p4rtc_port: Optional[str] = Field(default="51001")
    slice_id: Optional[int] = Field(default=0)
    default_tc: Optional[int] = Field(default=3)
    clear_state_on_restart: Optional[bool] = Field(default=False)

class UpfJsonc(NFVCLBaseModel):
    mode: Optional[str] = Field(default="af_packet")
    workers: Optional[int] = Field(default=1)
    log_level: Optional[str] = Field(default="info")
    hwcksum: Optional[bool] = Field(default=False)
    gtppsc: Optional[bool] = Field(default=False)
    ddp: Optional[bool] = Field(default=False)
    max_req_retries: Optional[int] = Field(default=5)
    resp_timeout: Optional[str] = Field(default="2s")
    enable_ntf: Optional[bool] = Field(default=False)
    enable_p4rt: Optional[bool] = Field(default=False)
    enable_hbTimer: Optional[bool] = Field(default=False)
    enable_gtpu_path_monitoring: Optional[bool] = Field(default=False)
    p4rtciface: P4rtciface
    max_sessions: Optional[int] = Field(default=50000)
    table_sizes: TableSizes
    access: UpfJsoncInterface  # N3
    core: UpfJsoncInterface  # N6
    n4: UpfJsoncInterface
    measure_upf: Optional[bool] = Field(default=True)
    measure_flow: Optional[bool] = Field(default=False)
    enable_notify_bess: Optional[bool] = Field(default=True)
    notify_sockaddr: Optional[str] = Field(default="/pod-share/notifycp")
    cpiface: Cpiface
    slice_rate_limit_config: SliceRateLimitConfig
    qci_qos_config: List[QciQosConfigItem]


class CfgFiles(NFVCLBaseModel):
    upf_jsonc: UpfJsonc = Field(..., alias='upf.jsonc')


class Upf(NFVCLBaseModel):
    privileged: Optional[bool] = Field(default=True)
    prometheus: Prometheus
    hugepage: Hugepage
    sriov: Sriov
    ipam: str = Field(default="static")
    cni_plugin: str = Field(default="macvlan", alias='cniPlugin')
    enb: Enb
    access: UpfInterface
    core: UpfInterface
    n4: UpfInterface
    cfg_files: CfgFiles = Field(..., alias='cfgFiles')


class Config(NFVCLBaseModel):
    upf: Upf


class SdcoreK8sUpfConfig(NFVCLBaseModel):
    config: Optional[Config] = None
