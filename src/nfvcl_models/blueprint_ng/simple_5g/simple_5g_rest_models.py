from enum import StrEnum
from typing import List, Optional

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core_models.custom_types import AreaIDType
from nfvcl_core_models.resources import VmResourceFlavor


class Simple5GAreaWorkers(NFVCLBaseModel):
    replicas: int = Field(default=1, description="Number of workers in this area")
    flavor: Optional[VmResourceFlavor] = Field(default_factory=VmResourceFlavor)

class Simple5GCoreImplEnum(StrEnum):
    SDCORE = 'sdcore'
    FREE5GC = 'free5gc'
    OAI = 'oai'

class Simple5GArea(NFVCLBaseModel):
    id: AreaIDType = Field(description="The area in witch the deployment is made, VMs are created")
    workers: Optional[Simple5GAreaWorkers] = Field(default_factory=Simple5GAreaWorkers)
    core_implementation: Simple5GCoreImplEnum = Field(description="The core implementation to be used in this area")
    num_ues: int = Field(gt=0, description="Number of UEs to be created in this area")

class Simple5GCreateModel(BlueprintNGCreateModel):
    mgmt_net: str = Field(description="The management network")
    force_pods_on_area: Optional[bool] = Field(default=False, description="Force pods on k8s worker with same area")
    areas: List[Simple5GArea] = Field(min_length=1, description="List of areas in witch deployment is made (with requirements)")
