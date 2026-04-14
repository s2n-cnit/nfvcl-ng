from __future__ import annotations

import ipaddress
from typing import Any, List, Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel


class Path(NFVCLBaseModel):
    file: str


class Logger(NFVCLBaseModel):
    path: Path
    level: str


class PcfpServerItem(NFVCLBaseModel):
    address: str


class Pfcp(NFVCLBaseModel):
    server: List[PcfpServerItem]
    node_id: str
    client: Optional[Any] = None


class GtpuServerItem(NFVCLBaseModel):
    address: str


class Gtpu(NFVCLBaseModel):
    server: List[GtpuServerItem]


class SessionItem(NFVCLBaseModel):
    subnet: str
    gateway: str
    dnn: Optional[str] = None


class MetricsServerItem(NFVCLBaseModel):
    dev: str
    port: int


class Metrics(NFVCLBaseModel):
    server: List[MetricsServerItem]


class Upf(NFVCLBaseModel):
    pfcp: Pfcp
    gtpu: Gtpu
    session: List[SessionItem]
    metrics: Optional[Metrics] = None


class Open5gsUpfConfig(NFVCLBaseModel):
    logger: Optional[Logger] = None
    global_: Optional[Any] = Field(None, alias='global')
    upf: Optional[Upf] = None

    def add_session(self, dnn: str, cidr: str):
        ip = ipaddress.ip_network(cidr)
        session = SessionItem(
            subnet=cidr,
            gateway=ip[1].exploded,
            dnn=dnn)
        if session not in self.upf.session:
            self.upf.session.append(session)
