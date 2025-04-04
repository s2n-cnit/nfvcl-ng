from enum import Enum
from typing import Optional, List

from pydantic import Field
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.plugin_k8s_model import K8sOperationType


class NfvoStatus(str, Enum):
    ONBOARDED = "onboarded"
    NOT_ONBOARDED = "not_onboarded"
    ONBOARDING = 'onboarding'
    ERROR = 'error'


class K8sVersion(str, Enum):
    """
    This class represents a k8s version. This should represent supported versions of k8s clusters by k8s manager.
    It has the utilities for checking if the version is present and to compare versions.
    """
    V1_24 = 'v1.24'
    V1_25 = 'v1.25'
    V1_26 = 'v1.26'
    V1_27 = 'v1.27'
    V1_28 = 'v1.28'
    V1_29 = 'v1.29'
    V1_30 = 'v1.30'

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_

    def is_minor(self, to_compare) -> bool:
        """
        Check if this version is less than another

        Args:
            to_compare: the K8sVersion to be compared to this one

        Returns:
            true if this is minor
        """
        if not isinstance(to_compare, K8sVersion):
            return NotImplemented
        this_version = self.value[1:]
        other_version = to_compare.value[1:]
        return float(this_version) < float(other_version)

class ProvidedBy(str, Enum):
    """
    This class represents a k8s version. This should represent supported versions of k8s clusters by k8s manager.
    It has the utilities for checking if the version is present and to compare versions.
    """
    NFVCL = 'NFVCL'
    EXTERNAL = 'EXTERNAL'
    UNKNOWN = 'UNKNOWN'


class K8sNetworkInfo(NFVCLBaseModel):
    name: str = Field(description="The name of the network to be used by the k8s cluster. This name should be the same of one network in the topology. This allow to assign IP pools from the Topology to the k8s cluster automatically.")
    interface_name: Optional[str] = Field(default=None, description="The name of the interface connected to this network. The interface name must be same for all nodes in the cluster.")
    multus_enabled: Optional[bool] = Field(default=False, description="If true, the network is a Multus network")
    ip_pools: Optional[List[str]] = Field(default_factory=list, description="The list of IP pools ids that can be used by blueprints to deploy services. The IP pools must be assigned by the topology.")

class TopologyK8sModel(NFVCLBaseModel):
    name: str = Field(title="Name of k8s cluster", description="It must be unique for each k8s cluster")
    provided_by: ProvidedBy = Field(default=ProvidedBy.NFVCL.value, description="The provider of the cluster")
    blueprint_ref: str = Field(default="", description="Reference blueprint, empty if k8s cluster is external")
    deployed_blueprints: List[str] = Field(default=[], description="The list of Blueprints deployed in k8s cluster")
    credentials: str = Field(title="Content of k8s credential file (example admin.conf)")
    vim_name: Optional[str] = Field(default=None, description="Reference VIM, where k8s cluster is deployed.")
    k8s_version: K8sVersion = Field(default=K8sVersion.V1_30, description="The version of the k8s cluster")
    networks: List[K8sNetworkInfo] = Field(description="List of attached networks to the cluster")
    areas: List[int] = Field(description="Competence areas of the k8s cluster", min_length=1)
    cni: Optional[str] = Field(default=None, description="The CNI plugin used in the cluster")
    cadvisor_node_port: Optional[int] = Field(default=None, description="The node port on which the cadvisor service is exposed")
    nfvo_status: NfvoStatus = Field(default=NfvoStatus.NOT_ONBOARDED, deprecated=True) # TODO remove
    nfvo_onboard: bool = Field(default=False, deprecated=True) # TODO remove
    anti_spoofing_enabled: Optional[bool] = Field(default=False)

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, TopologyK8sModel):
            return self.name == other.name
        return False

    def get_network(self, network_name: str) -> K8sNetworkInfo:
        """
        Returns the desired network if connected to the cluster
        Args:
            network_name: The desired network

        Returns:
            The network if attached to the cluster, None otherwise
        """
        for network in self.networks:
            if network.name == network_name:
                return network
        raise ValueError(f"Network is not present in {self.name} K8S cluster")

    def release_ip_pool(self, ip_pool_name: str):
        """
        Release the IP pools from the network info
        Args:
            ip_pool_name: The name of the IP pool to be released
        """
        for network in self.networks:
            if ip_pool_name in network.ip_pools:
                network.ip_pools.remove(ip_pool_name)
                return
        raise ValueError(f"IP pool {ip_pool_name} is not present in {self.name} K8S cluster")

class K8sModelCreateFromBlueprint(NFVCLBaseModel):
    """
    Model used to insert an existing k8s cluster, created with the NFVCL blueprint, into the topology.
    """
    name: str = Field(description="The name to be given at the cluster in the topology.")
    nfvo_onboard: bool = Field(default=False, description="If true the cluster is onboarded into OSM")
    blueprint_ref: str = Field(description="The ID of the k8s blueprint")


class K8sModelManagement(NFVCLBaseModel):
    """
    Model to support message exchange from NFVCL core and K8S management (through Redis sub/pub)
    """
    k8s_ops: K8sOperationType = Field(description="Type of operation to be applied at the desired cluser")
    cluster_id: str = Field(description="The identifier of the k8s cluster")
    data: str = Field(description="Data to be parsed, change depending on the operation type")
    options: dict = Field(default={}, description="Hold optional parameters for k8s management")


class K8sQuota(NFVCLBaseModel):
    """
    Model used to add a quota reservation (for resources) to a namespace.
    """
    request_cpu: str = Field(default="1", alias="requests.cpu")
    request_memory: str = Field(default="1Gi", alias="requests.memory")
    limit_cpu: str = Field(default="2", alias="limits.cpu")
    limit_memory: str = Field(default="2Gi", alias="limits.memory")
