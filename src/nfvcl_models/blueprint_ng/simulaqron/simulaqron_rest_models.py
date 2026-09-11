from typing import List

from pydantic import Field

from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core_models.resources import VmResourceFlavor


class SimulaqronCreateModel(BlueprintNGCreateModel):
    """
    This class represents the model for the creation request of a Simulaqron Blueprint
    """
    area: int = Field(description="The area in which the VM is deployed")
    password: str = Field(default="ubuntu", description="The password to be set", pattern=r'^[a-zA-Z0-9_.-]*$')
    mgmt_net: str = Field(description="The management network of the Simulaqron VM")
    data_nets: List[str] = Field(default=[], description="The data network to be connected at Simulaqron VM")
    flavor: VmResourceFlavor = Field(default=VmResourceFlavor(), description="Optional flavors, if flavor.name is specified it will try to use this the existing flavor")
