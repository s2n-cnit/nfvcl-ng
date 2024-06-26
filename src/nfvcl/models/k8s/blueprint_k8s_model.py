from typing import List, Optional, Literal, Dict
from pydantic import Field
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.k8s.common_k8s_model import LBPool, Cni
from nfvcl.models.k8s.topology_k8s_model import K8sModel, K8sVersion
from nfvcl.models.virtual_link_desc import VirtLinkDescr
from nfvcl.models.vim.vim_models import VMFlavors


class K8sNetworkEndpoints(NFVCLBaseModel):
    mgt: str = Field(
        ..., description='The name of the topology network to be used for management'
    )
    mgt_internal: Optional[str] = None
    data_nets: List[LBPool] = Field(description='topology networks to be used by the load balancer', min_length=1)


class K8sNsdInterfaceDesc(NFVCLBaseModel):
    nsd_id: str
    nsd_name: str
    vld: List[VirtLinkDescr]


class K8sAreaInfo(NFVCLBaseModel):
    id: int
    core: Optional[bool] = False
    workers_replica: int
    worker_flavor_override: Optional[VMFlavors] = Field(default=None)
    worker_mgt_int: Dict[str, K8sNsdInterfaceDesc] = Field(default={})
    worker_data_int: Dict[str, K8sNsdInterfaceDesc] = Field(default={})


class K8sConfig(NFVCLBaseModel):
    version: K8sVersion = Field(default=K8sVersion.V1_28)
    cni: Cni = Field(default=Cni.flannel)
    linkerd: dict = Field(default={})
    pod_network_cidr: str = Field(default="10.254.0.0/16", description='K8s Pod network IPv4 cidr to init the cluster')
    network_endpoints: K8sNetworkEndpoints
    worker_flavors: VMFlavors = VMFlavors()
    master_flavors: VMFlavors = VMFlavors()
    nfvo_onboard: bool = False
    core_area: Optional[K8sAreaInfo] = Field(default=None, description="The core are of the cluster")
    controller_ip: str = Field(default="", description="The IP of the k8s controller or master, reachable from the outside (es. floating IP)")
    controller_internal_ip: Optional[str] = Field(default=None, description="The IP of the k8s controller or master, in the internal net")
    master_key_add_worker: str = Field(default="", description="The master key to be used by a worker to join the k8s cluster")
    master_credentials: str = Field(default="", description="The certificate of the admin, to allow k8s administration")

    class Config:
        use_enum_values = True


class K8sBlueprintCreate(NFVCLBaseModel):
    type: Literal['K8sBlue']
    callbackURL: Optional[str] = Field(None, description='url that will be used to notify when the blueprint processing finishes')
    config: K8sConfig
    areas: List[K8sAreaInfo] = Field(..., description='list of areas to instantiate the Blueprint', min_length=1)

    class Config:
        use_enum_values = True


class K8sBlueprintModel(K8sBlueprintCreate):
    """
    Model used to represent the K8s Blueprint instance. It EXTENDS the model for k8s blueprint creation
    K8sBlueprintCreate
    """
    blueprint_instance_id: str = Field(description="The blueprint ID generated when it has been instantiated")
    vim_name: Optional[str] = Field(default=None)

    def parse_to_k8s_topo_model(self, vim_name: str = None) -> K8sModel:
        """
        Parse the blueprint model to the topology representation
        Args:
            vim_name: The vim name
        Returns:
            The parsed model.
        """
        k8s_data: K8sModel = K8sModel(
            name=self.blueprint_instance_id,
            provided_by='blueprint',
            blueprint_ref=self.blueprint_instance_id,
            k8s_version=self.config.version,
            credentials=self.config.master_credentials,
            vim_name=vim_name if vim_name else self.vim_name,
            networks=[item.net_name for item in self.config.network_endpoints.data_nets],
            areas=[item.id for item in self.areas],
            cni=self.config.cni,
            nfvo_onboard=self.config.nfvo_onboard)
        return k8s_data


class K8sBlueprintScale(NFVCLBaseModel):
    callbackURL: Optional[str] = Field(
        None,
        description='URL that will be used to notify when the blueprint processing finishes',
    )
    operation: Literal['scale']
    add_areas: List[K8sAreaInfo]
    modify_areas: List[K8sAreaInfo]
    del_areas: List[K8sAreaInfo]


