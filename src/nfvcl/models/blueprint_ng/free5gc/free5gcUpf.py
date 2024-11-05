from __future__ import annotations

from typing import List

from pydantic import Field

from nfvcl.models.base_model import NFVCLBaseModel


class Pfcp(NFVCLBaseModel):
    addr: str
    node_id: str = Field(..., alias='nodeID')
    retrans_timeout: str = Field(..., alias='retransTimeout')
    max_retrans: int = Field(..., alias='maxRetrans')


class IfListItem(NFVCLBaseModel):
    addr: str
    type: str


class Gtpu(NFVCLBaseModel):
    forwarder: str
    if_list: List[IfListItem] = Field(..., alias='ifList')


class DnnListItem(NFVCLBaseModel):
    dnn: str
    cidr: str


class Logger(NFVCLBaseModel):
    enable: bool
    level: str
    report_caller: bool = Field(..., alias='reportCaller')


class Free5gcUpfConfig(NFVCLBaseModel):
    version: str
    description: str
    pfcp: Pfcp
    gtpu: Gtpu
    dnn_list: List[DnnListItem] = Field(..., alias='dnnList')
    logger: Logger
