from typing import List

from pydantic import Field

from nfvcl_models.blueprint_ng.common import UbuntuVersion
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core_models.resources import VmResourceFlavor


class UbuntuCreateModel(BlueprintNGCreateModel):
    """
    This class represents the model for the creation request of a DNS Blueprint
    """
    area: int = Field(description="The area in witch the VM is deployed")
    password: str = Field(default="ubuntu", description="The password to be set", pattern=r'^[a-zA-Z0-9_.-]*$')
    mgmt_net: str = Field(description="The management network of the DNS server")
    version: UbuntuVersion = Field(default=UbuntuVersion.UBU24, description="Version of Ubuntu")
    data_nets: List[str] = Field(default=[], description="The data network to be connected at ubuntu VM")
    flavor: VmResourceFlavor = Field(default=VmResourceFlavor(), description="Optional flavors, if flavor.name is specified it will try to use this the existing flavor")
