from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class TopologyWorkerOperation(Enum):
    ADD_TOPOLOGY = "add_topology"
    DEL_TOPOLOGY = "del_topology"
    ADD_VIM = "add_vim"
    DEL_VIM = "del_vim"
    UPDATE_VIM = "update_vim"
    ADD_NET = "add_net"
    DEL_NET = "del_net"
    ADD_ROUTER = "add_router"
    DEL_ROUTER = "del_router"
    ADD_PDU = "add_pdu"
    DEL_PDU = "del_pdu"
    ADD_K8S = "add_k8s"
    DEL_K8S = "del_k8s"
    UPDATE_K8S = "update_k8s"
    ADD_PROM = "add_prom"
    DEL_PROM = "del_prom"
    UPD_PROM = "upd_prom"


class TopologyWorkerMessage(BaseModel):
    ops_type: TopologyWorkerOperation
    data: dict
    optional_data: Optional[dict] = Field(default=None)
    callback: Optional[str] = Field(default=None)
