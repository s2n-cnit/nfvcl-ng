from __future__ import annotations

from typing import List

from blueprints_ng.resources import VmResourceFlavor
from pydantic import Field, field_validator, PositiveInt

from blueprints.blue_vyos import VyOSSourceNATRule
from blueprints_ng.blueprint_ng import BlueprintNGCreateModel
from models.base_model import NFVCLBaseModel


class K8sAreaDeployment(NFVCLBaseModel):
    area_id: int = Field(description="The area in witch the deployment is made")
    is_master_area: bool = Field(default=False, description="If true the master is deployed in this area")
    mgmt_net: str = Field(description="The management network") # TODO validate
    service_net: str = Field(min_items=1, description="Network on witch services are exposed") # TODO validate
    service_net_required_ip_number: int = Field(default=20, description="The required IPs number to exposed services, they should be reserved")
    worker_replicas: PositiveInt = Field(default=1, description="Number of workers in this area")
    worker_flavors: VmResourceFlavor = VmResourceFlavor(memory_mb="8192", storage_gb='32', vcpu_count='6')

class K8sCreateModel(BlueprintNGCreateModel):
    """
    This class represents the model for the creation request
    """
    cni: str # TODO validate
    pod_network_cidr: str = Field(default="10.254.0.0/16", description='K8s Pod network IPv4 cidr to init the cluster') # TODO validate
    topology_onboard: bool = True

    master_flavors: VmResourceFlavor = VmResourceFlavor(memory_mb="2048", storage_gb='16', vcpu_count='2')
    areas: List[K8sAreaDeployment] = Field(min_items=1, description="List of areas in witch deployment is made (with requirements)")

    @field_validator('areas')
    @classmethod
    def check_areas(cls, areas: List[K8sAreaDeployment]) -> List[K8sAreaDeployment]:
        if isinstance(areas, list):
            if len([area for area in areas if area.is_master_area == True]) < 1:
                raise ValueError("There must be a master area to be deployed. Please set is_master_area to true at least in one area.")
            if len([area for area in areas if area.is_master_area == True]) > 1:
                raise ValueError("There must be ONLY a master area to be deployed. Please check area list")

        return areas



class VyOSBlueprintSNATCreate(NFVCLBaseModel):
    rule: VyOSSourceNATRule
