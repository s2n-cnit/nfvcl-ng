from __future__ import annotations
from typing import List, Optional
from models.k8s.common_k8s_model import Cni
from blueprints_ng.resources import VmResourceFlavor
from pydantic import Field, field_validator, PositiveInt, model_validator
from blueprints_ng.blueprint_ng import BlueprintNGCreateModel
from models.base_model import NFVCLBaseModel


class K8sAreaDeployment(NFVCLBaseModel):
    area_id: int = Field(description="The area in witch the deployment is made")
    is_master_area: bool = Field(default=False, description="If true the master is deployed in this area")
    mgmt_net: str = Field(description="The management network") # TODO validate
    service_net: Optional[str] = Field(default=None, min_items=1, description="Network on witch services are exposed. If not present, service are exposed to an internal net (that can be accessed thought a VXLAN tunnel)")
    service_net_required_ip_number: int = Field(default=20, description="The required IPs number to exposed services, they should be reserved. USED only in master area")
    worker_replicas: PositiveInt = Field(default=1, description="Number of workers in this area")
    worker_flavors: VmResourceFlavor = VmResourceFlavor(memory_mb="8192", storage_gb='32', vcpu_count='6')

    def __eq__(self, other):
        """
        Two areas are identical if they have the same ID
        """
        if isinstance(other, K8sAreaDeployment):
            return self.area_id == other.area_id
        return False

    @model_validator(mode='after')
    def check_service_net(self) -> K8sAreaDeployment:
        """
        Checks if the service net is present, and it is the master area. We choose to expose services only in master area (where the controller is located)
        """
        if not self.service_net:
            return self
        if self.service_net:
            # TODO check if net exist
            if self.is_master_area == False:
                raise ValueError("Service net should be only present in master area")
            return self

class K8sCreateModel(BlueprintNGCreateModel):
    """
    This class represents the model for the creation request
    """
    cni: Cni = Field(default=Cni.flannel.value)
    pod_network_cidr: str = Field(default="10.254.0.0/16", description='K8s Pod network IPv4 cidr to init the cluster') # TODO validate
    service_cidr: str = Field(default="10.200.0.0/16", description='Network used to deploy services') # TODO validate
    topology_onboard: bool = True
    password: str = Field(default="ubuntu", description="The password to be set, in every vm, for user ubuntu", pattern=r'^[a-zA-Z0-9_.-]*$')
    install_plugins: bool = Field(default=True, description="Whether to install default plugin list on blueprint deployment (Flannel, MetalLb, OpenEBS)")
    master_flavors: VmResourceFlavor = VmResourceFlavor(memory_mb="2048", storage_gb='16', vcpu_count='2')
    areas: List[K8sAreaDeployment] = Field(min_items=1, description="List of areas in witch deployment is made (with requirements)")

    @field_validator('areas')
    @classmethod
    def check_areas(cls, areas: List[K8sAreaDeployment]) -> List[K8sAreaDeployment]:
        if isinstance(areas, list):
            master_areas = [area for area in areas if area.is_master_area == True]
            if len(master_areas) < 1:
                raise ValueError("There must be a master area to be deployed. Please set is_master_area to true at least in one area.")
            if len(master_areas) > 1:
                raise ValueError("There must be ONLY a master area to be deployed. Please check area list")

        return areas

    def get_master_area(self) -> K8sAreaDeployment | None:
        """
        Returns the master area of the request
        """
        master_areas = [area for area in self.areas if area.is_master_area == True]
        if len(master_areas) > 0:
            return master_areas[0]
        else:
            return None


class K8sAddNodeModel(BlueprintNGCreateModel):
    areas: List[K8sAreaDeployment] = Field(min_items=1, description="List of areas in witch deployment is made (with requirements)")

    @field_validator('areas')
    @classmethod
    def check_areas(cls, areas: List[K8sAreaDeployment]) -> List[K8sAreaDeployment]:
        """
        Checks if there is NOT a master area in day2 call
        """
        if isinstance(areas, list):
            if len([area for area in areas if area.is_master_area == True]) >= 1:
                raise ValueError("It is not possible to add CORE areas in day2 request. Only upon cluster creation.")

        return areas

class K8sDelNodeModel(BlueprintNGCreateModel):
    node_names: List[str] = Field(min_items=1, description="List of nodes names (1VSVPN_VM_K8S_C) to be removed from the cluster")

class KarmadaInstallModel(BlueprintNGCreateModel):
    """
    Model for Karmada and Submarine installation and configuration. It contains required parameters for the configuration.
    """
    cluster_id: str = Field(description="Name of the current cluster Submariner and Karmada. Must be unique", pattern="[a-z0-9]([-a-z0-9]*[a-z0-9])?")
    kube_config_location: str = Field(default="/root/.kube/config",description="Path to local kubeconfig (on the master node)")
    submariner_broker: str = Field(description="Content of the submariner broker file (.subm file extension)")
    karmada_control_plane: str = Field(description="The IP and port of Karmada")
    karmada_token: str = Field(description="The Karmada token")
    discovery_token_hash: str = Field(description="Discovery token hash")

class CreateVxLanModel(NFVCLBaseModel):
    """
    Model used to request a VxLan tunnel to interact with internal k8s networks if needed.
    """
    vx_name: str = Field(description="The name of the VxLan")
    vxid: str = Field(description="The VxLan ID")
    vx_client_ip: str = Field(description="The remote IP that want to be connected with the K8S internal network")
    vx_server_ip: Optional[str] = Field(default=None, description="The local IP on the K8S side where the VxLAN is listening")
    vx_server_ext_device: Optional[str] = Field(default=None, description="The name of the interface where the VxLan is listening")
    vx_server_ext_port: str = Field(default="4789")
    vxlan_server_int_cidr: str = Field(description="The CIDR of the VxLan, e.g. 10.234.154.0/24")
