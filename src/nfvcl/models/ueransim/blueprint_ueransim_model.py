from enum import Enum
from typing import List, Any

from pydantic import Field, constr, ConfigDict

from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.vim.vim_models import VimNetMap


class UeransimNetworkEndpoints(NFVCLBaseModel):
    mgt: str = Field(..., description='name of the topology network to be used for management')
    n2: str = Field(..., description='name of the topology network to be used by NodeBs to attach the core network')
    n3: str = Field(..., description='name of the topology network to be used by NodeBs to attach the core network')

class UeransimConfig(NFVCLBaseModel):
    network_endpoints: UeransimNetworkEndpoints


class UeransimConfiguredNssaiItem(NFVCLBaseModel):
    sst: int
    sd: int


class UeransimDefaultNssaiItem(NFVCLBaseModel):
    sst: int
    sd: int


class UeransimSlice(NFVCLBaseModel):
    sst: int
    sd: int

class PDUSessionType(Enum):
    IPv4 = 'IPv4'
    IPv6 = 'IPv6'


class UeransimSession(NFVCLBaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Allow creating model object using the field name instead of the alias
        use_enum_values=True,  # Needed to be able to save the state to the mongo DB
        validate_default=True
    )

    type: PDUSessionType
    apn: str
    slice: UeransimSlice

class OpType(Enum):
    OPC = 'OPC'

class UeransimSim(NFVCLBaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Allow creating model object using the field name instead of the alias
        use_enum_values=True,  # Needed to be able to save the state to the mongo DB
        validate_default=True
    )

    imsi: constr(pattern=r'^[0-9]*$', min_length=15, max_length=15)
    plmn: constr(pattern=r'^[0-9]*$', min_length=5, max_length=5)
    key: constr(pattern=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    op: constr(pattern=r'^[a-fA-F0-9]+$', min_length=32, max_length=32)
    opType: OpType
    amf: constr(min_length=4, max_length=4) | None = None
    configured_nssai: List[UeransimConfiguredNssaiItem] | None = Field(None, min_items=1)
    default_nssai: List[UeransimDefaultNssaiItem] | None= Field(None, min_items=1)
    sessions: List[UeransimSession] | None = Field(None, min_items=1)


class UeransimUe(NFVCLBaseModel):
    id: int = Field(None, description='UE identifier')
    sims: List[UeransimSim] = Field(None, description='List of sims in the current UE virtual machine')
    vim_gnbs_ips: List[str] = Field(default=[], description="List of IP of gNBs")

    def __eq__(self, other: Any) -> bool:
        """
        Override equals. IF the id is the same, they are the same area
       Args:
            other: the object to be compared

        Returns:
            True if id is the same
        """
        if isinstance(other, UeransimUe):
            if other.id == self.id:
                return True
        return False


class UeransimArea(NFVCLBaseModel):
    id: int = Field(..., description='Area identifier, it will be used as TAC in the NodeB configuration')
    nci: str | None = Field(None, description='gNodeB nci identifier')
    idLength: int | None = Field(None, description='gNodeB nci identifier length')
    ues: List[UeransimUe] = Field(description='list of virtual UEs to be instantiated')
    gnb_interface_list: List[VimNetMap] = Field(default=[], description="List of gnb interfaces, each area has one gNB")

    def __eq__(self, other: Any) -> bool:
        """
        Override equals. IF the id is the same, they are the same area
        Args:
            other: the object to be compared

        Returns:
            True if id is the same
        """
        if isinstance(other, UeransimArea):
            if other.id == self.id:
                return True
        return False


class UeransimModel(NFVCLBaseModel):
    type: str
    config: UeransimConfig
    areas: List[UeransimArea]

