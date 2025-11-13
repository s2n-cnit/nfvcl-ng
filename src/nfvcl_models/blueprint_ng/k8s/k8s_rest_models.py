

from enum import Enum
from typing import List, Optional

from nfvcl_models.blueprint_ng.common import UbuntuVersion
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address, SerializableIPv4Network
from nfvcl_core_models.resources import VmResourceFlavor
from pydantic import Field, field_validator, PositiveInt
from nfvcl_common.base_model import NFVCLBaseModel


class K8sAreaDeployment(NFVCLBaseModel):
    area_id: int = Field(description="The area in witch the deployment is made, VMs are created")
    is_master_area: bool = Field(default=False, description="If true, the master/controller is deployed in this area. Only one area can be master.")
    mgmt_net: str = Field(description="The management network NAME in the topology used by NFVCL to configure nodes")
    additional_networks: List[str] = Field(default=[], description="Additional networks connected to the VMs in this area")

    load_balancer_pools_ips: List[SerializableIPv4Address] = Field(default=[], description="The list of IPs to be announced at L2 from the load balancer IN THIS AREA.")

    worker_replicas: PositiveInt = Field(default=1, description="Number of workers in this area")
    worker_flavors: VmResourceFlavor = VmResourceFlavor(memory_mb="8192", storage_gb='32', vcpu_count='6')

    def __eq__(self, other):
        """
        Two areas are identical if they have the same ID
        """
        if isinstance(other, K8sAreaDeployment):
            return self.area_id == other.area_id
        return False


class Cni(str, Enum):
    flannel = 'flannel'
    calico = 'calico'


class K8sCreateModel(BlueprintNGCreateModel):
    """
    This class represents the model for the creation request of a K8S Blueprint
    """
    cni: Cni = Field(default=Cni.flannel.value)
    pod_network_cidr: SerializableIPv4Network = Field(default=SerializableIPv4Network("10.254.0.0/16"), description='K8s Pod network IPv4 cidr to init the cluster')
    service_cidr: SerializableIPv4Network = Field(default=SerializableIPv4Network("10.200.0.0/16"), description='Network used to deploy services')
    topology_onboard: bool = Field(default=True, description="If true the K8S cluster, once ready, will be added to the Topology of NFVCL to be used for Blueprint, that requires k8s, creation.")
    containerd_mirrors: Optional[dict[str, str]] = Field(default=None, description="Dict of containerd mirrors (cache) to be added to the configuration of containerd to avoid limitations from docker.io or other public repositories. Key is the registry, value is the mirror (e.g. {'docker.io': 'https://docker-registry.tnt-lab.unige.it/v2/cache/'})")
    password: str = Field(default="ubuntu", description="The password to be set, in every vm, for user ubuntu", pattern=r'^[a-zA-Z0-9_.-]*$')
    ubuntu_version: UbuntuVersion = Field(default=UbuntuVersion.UBU24, description="Version of Ubuntu")
    install_plugins: bool = Field(default=True, description="Whether to install default plugin list on blueprint deployment (default Flannel, MetalLb, OpenEBS)")
    enable_multus: Optional[bool] = Field(default=False, description="Whether to enable Multus plugin (default false), additional checks and limitations are applied")
    cadvisor_node_port: int = Field(default=30080, ge=30000, le=32767, description="The node port on which the cadvisor service is exposed")
    master_flavors: VmResourceFlavor = VmResourceFlavor(memory_mb="2048", storage_gb='16', vcpu_count='2')
    require_port_security_disabled: Optional[bool] = Field(default=True, description="Global port security disable, override port security in nodes flavors, required for MetalLB (multiple IP not declared on openstack)")
    areas: List[K8sAreaDeployment] = Field(min_length=1, description="List of areas in witch deployment is made (with requirements)")

    @field_validator('areas')
    def check_areas(cls, areas: List[K8sAreaDeployment]) -> List[K8sAreaDeployment]:
        if isinstance(areas, list):
            master_areas = [area for area in areas if area.is_master_area]
            if len(master_areas) < 1:
                raise ValueError("There must be a master area to be deployed. Please set is_master_area to true at least in one area.")
            if len(master_areas) > 1:
                raise ValueError("There must be ONLY a master area to be deployed. Please check area list")

        return areas

    def get_master_area(self) -> K8sAreaDeployment | None:
        """
        Returns the master area of the request
        """
        master_areas = [area for area in self.areas if area.is_master_area]
        if len(master_areas) > 0:
            return master_areas[0]
        else:
            return None


class K8sAddNodeModel(BlueprintNGCreateModel):
    areas: List[K8sAreaDeployment] = Field(min_length=1, description="List of areas in witch deployment is made (with requirements)")

    @field_validator('areas')
    def check_areas(cls, areas: List[K8sAreaDeployment]) -> List[K8sAreaDeployment]:
        """
        Checks if there is NOT a master area in day2 call
        """
        if isinstance(areas, list):
            if len([area for area in areas if area.is_master_area]) >= 1:
                raise ValueError("It is not possible to add CORE areas in day2 request. Only upon cluster creation.")

        return areas

class K8sDelNodeModel(BlueprintNGCreateModel):
    node_names: List[str] = Field(min_length=1, description="List of nodes names (e.g. 1VSVPN_VM_K8S_C) to be removed from the cluster")

class KarmadaInstallModel(BlueprintNGCreateModel):
    """
    Model for Karmada and Submarine installation and configuration. It contains required parameters for the configuration.
    """
    cluster_id: str = Field(description="Name of the current cluster Submariner and Karmada. Must be unique", pattern=r"[a-z0-9]([-a-z0-9]*[a-z0-9])?")
    kube_config_location: str = Field(default="/root/.kube/config",description="Path to local kubeconfig (on the master node)")
    submariner_broker: str = Field(description="Content of the submariner broker file (.subm file extension)")
    karmada_control_plane: str = Field(description="The IP and port of Karmada")
    karmada_token: str = Field(description="The Karmada token")
    discovery_token_hash: str = Field(description="Discovery token hash")
