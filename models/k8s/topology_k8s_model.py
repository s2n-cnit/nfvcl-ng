from enum import Enum
from typing import Optional, List

from pydantic import Field

from models.base_model import NFVCLBaseModel
from models.k8s.plugin_k8s_model import K8sOperationType


class NfvoStatus(Enum):
    ONBOARDED = "onboarded"
    NOT_ONBOARDED = "not_onboarded"
    ONBOARDING = 'onboarding'
    ERROR = 'error'


class K8sVersion(str, Enum):
    """
    This class represent a k8s version. This should represent supported versions of k8s clusters by k8s manager.
    It has the utilities for checking if the version is present and to compare versions.
    """
    V1_24 = 'v1.24'
    V1_25 = 'v1.25'
    V1_26 = 'v1.26'
    V1_27 = 'v1.27'
    V1_28 = 'v1.28'

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


class K8sModel(NFVCLBaseModel):
    name: str = Field(title="Name of k8s cluster. It must be unique for each k8s cluster")
    provided_by: str
    blueprint_ref: str = Field(default="", title="Reference blueprint, empty if k8s cluster is external")
    credentials: str = Field(title="Content of k8s crediential file (example admin.conf)")
    vim_name: Optional[str] = Field(default=None, title="Reference VIM, where k8s cluster is deployed.")
    k8s_version: K8sVersion = Field(default=K8sVersion.V1_24)
    networks: List[str] = Field(title="List of attached networks", min_items=1)
    areas: List[int] = Field(title="Competence areas", min_items=1)
    cni: Optional[str] = Field(default=None)
    nfvo_status: NfvoStatus = Field(default=NfvoStatus.NOT_ONBOARDED)
    nfvo_onboard: bool = Field(default=False)

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, K8sModel):
            return self.name == other.name
        return False


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
    request_cpu: str = Field(default=1, alias="requests.cpu")
    request_memory: str = Field(default="1Gi", alias="requests.memory")
    limit_cpu: str = Field(default=2, alias="limits.cpu")
    limit_memory: str = Field(default="2Gi", alias="limits.memory")
