from typing import List, Optional

from pydantic import Field

from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core_models.resources import VmResourceFlavor


class MonitoringCreateModel(BlueprintNGCreateModel):
    """
    This class represents the model for the creation request of a monitoring Blueprint
    """
    area: int = Field(description="The area in witch the VM is deployed")
    password: str = Field(default="ubuntu", description="The password to be set", pattern=r'^[a-zA-Z0-9_.-]*$')
    mgmt_net: str = Field(description="The management network of the DNS server")
    data_nets: List[str] = Field(default=[], description="The data network to be connected at ubuntu VM")
    flavor: VmResourceFlavor = Field(default=VmResourceFlavor(), description="Optional flavors, if flavor.name is specified it will try to use this the existing flavor")
    onboard_on_topology: Optional[bool] = Field(default=True)

