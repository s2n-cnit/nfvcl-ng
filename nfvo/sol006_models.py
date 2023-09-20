from pydantic import BaseModel, Field
from typing import Optional, List
from ipaddress import IPv4Address


class Sol006PDUInterface(BaseModel):
    name: str
    mgmt: bool
    ip_address: IPv4Address = Field(alias='ip-address')
    vim_network_name = str = Field(alias='vim-network-name')


class Sol006PDUrequest(BaseModel):
    name: str
    type: str
    description: Optional[str] = Field(default=None)
    shared: bool
    vims: List[dict] = []
    vim_accounts: List[dict] = []
    interfaces: List[Sol006PDUInterface]
