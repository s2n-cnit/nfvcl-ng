from __future__ import annotations

import ipaddress
from typing import List, Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_models.blueprint_ng.open5gs.core import MultusNetwork


class UpfPfcp(NFVCLBaseModel):
    address: str
    advertise: str
    node_id: str = Field(..., alias='nodeID')


class UpfGtpu(NFVCLBaseModel):
    address: str
    advertise: str


class UpfSubnetItem(NFVCLBaseModel):
    subnet: str
    gateway: str
    dnn: str
    dev: Optional[str] = Field(default="ogstun", alias='dev')
    mask: int
    enable_nat: bool = Field(default=False, alias='enableNAT')


class UpfK8sUpf(NFVCLBaseModel):
    pfcp: UpfPfcp
    gtpu: UpfGtpu
    gnb_subnet: str = Field(..., alias='gnbSubnet')


class UpfK8sInnerConfig(NFVCLBaseModel):
    log_level: str = Field("debug", alias='logLevel')
    upf: UpfK8sUpf
    subnet_list: List[UpfSubnetItem] = Field(..., alias='subnetList')

    def add_session(self, dnn: str, cidr: str):
        ip = ipaddress.ip_network(cidr)
        session = UpfSubnetItem(
            subnet=cidr,
            gateway=ip[1].exploded,
            dnn=dnn,
            mask=ip.prefixlen
        )
        if session not in self.subnet_list:
            self.subnet_list.append(session)


class UpfK8sMultus(NFVCLBaseModel):
    enabled: bool
    n3network: Optional[MultusNetwork] = None
    n4network: Optional[MultusNetwork] = None
    n6network: Optional[MultusNetwork] = None
    network_attachments: List = Field(default_factory=list, alias='networkAttachments')


class Open5GsUpfK8sConfig(NFVCLBaseModel):
    config: UpfK8sInnerConfig
    multus: UpfK8sMultus
