from typing import List
from pydantic import BaseModel, Field

from models.base_model import NFVCLBaseModel
from models.network import PduModel, PduInterface


class OSMPduInterface(NFVCLBaseModel):
    name: str
    ip_address: str = Field(..., alias='ip-address')
    vim_network_name: str = Field(..., alias='vim-network-name')
    mgmt: bool

    @classmethod
    def build_from_topology_pdu_interface(cls, topo_pdu_interface: PduInterface):
        return OSMPduInterface(name=topo_pdu_interface.name, ip_address=topo_pdu_interface.ip_address, vim_network_name=topo_pdu_interface.network_name, mgmt=topo_pdu_interface.mgt)


class OSMPduModel(NFVCLBaseModel):
    type: str
    name: str
    shared: bool = True
    vim_accounts: List[str]
    interfaces: List[OSMPduInterface]

    @classmethod
    def build_from_topology_pdu(cls, topo_pdu: PduModel, vim_accounts_ids=None):
        if vim_accounts_ids is None:
            vim_accounts_ids = []

        interfaces = []
        for to_be_conv in topo_pdu.interface:
            interfaces.append(OSMPduInterface.build_from_topology_pdu_interface(to_be_conv))

        return OSMPduModel(type=topo_pdu.type, name=topo_pdu.name, vim_accounts=vim_accounts, interfaces=interfaces)
