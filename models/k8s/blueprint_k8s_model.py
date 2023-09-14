from ipaddress import IPv4Network
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field, conlist
from models.k8s.common_k8s_model import LBPool, Cni
from models.k8s.topology_k8s_model import K8sModel, K8sVersion
from models.virtual_link_desc import VirtLinkDescr


class K8sNetworkEndpoints(BaseModel):
    mgt: str = Field(
        ..., description='name of the topology network to be used for management'
    )
    data_nets: List[LBPool] = Field(description='topology networks to be used by the load balancer', min_items=1)


class VMFlavors(BaseModel):
    memory_mb: str = Field(8192, alias='memory-mb')
    storage_gb: str = Field(12, alias='storage-gb')
    vcpu_count: str = Field(4, alias='vcpu-count')


class K8sNsdInterfaceDesc(BaseModel):
    nsd_id: str
    nsd_name: str
    vld: List[VirtLinkDescr]


class K8sAreaInfo(BaseModel):
    id: int
    core: Optional[bool] = False
    workers_replica: int
    worker_flavor_override: Optional[VMFlavors]
    worker_mgt_int: Dict[str, K8sNsdInterfaceDesc] = Field(default={})
    worker_data_int: Dict[str, K8sNsdInterfaceDesc] = Field(default={})


class K8sConfig(BaseModel):
    version: K8sVersion = Field(default=K8sVersion.V1_24)
    cni: Cni = Field(default=Cni.flannel)
    linkerd: Optional[dict]
    pod_network_cidr: Optional[IPv4Network] \
        = Field('10.254.0.0/16', description='K8s Pod network IPv4 cidr to init the cluster')
    network_endpoints: K8sNetworkEndpoints
    worker_flavors: VMFlavors = VMFlavors()
    master_flavors: VMFlavors = VMFlavors()
    nfvo_onboarded: bool = False
    core_area: K8sAreaInfo = Field(default=None, description="The core are of the cluster")
    controller_ip: str = Field(default="", description="The IP of the k8s controller or master")
    master_key_add_worker: str = Field(default="", description="The master key to be used by a worker to join the k8s cluster")
    master_credentials: str = Field(default="", description="The certificate of the admin, to allow k8s administration")

    class Config:
        use_enum_values = True


class K8sBlueprintCreate(BaseModel):
    type: Literal['K8s', 'K8sBeta']
    callbackURL: Optional[str] = Field(
        None,
        description='url that will be used to notify when the blueprint processing finishes',
    )
    config: K8sConfig
    areas: List[K8sAreaInfo] = Field(
        ...,
        description='list of areas to instantiate the Blueprint',
        min_items=1
    )

    class Config:
        use_enum_values = True


class K8sBlueprintModel(K8sBlueprintCreate):
    """
    Model used to represent the K8s Blueprint instance. It EXTENDS the model for k8s blueprint creation
    K8sBlueprintCreate
    """
    blueprint_instance_id: str = Field(description="The blueprint ID generated when it has been instantiated")

    def parse_to_k8s_topo_model(self, vim_name: str) -> K8sModel:
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
            vim_name=vim_name,
            networks=[item.net_name for item in self.config.network_endpoints.data_nets],
            areas=[item.id for item in self.areas],
            cni=self.config.cni,
            nfvo_onboarded=False)
        return k8s_data


class K8sBlueprintScale(BaseModel):
    callbackURL: Optional[str] = Field(
        None,
        description='URL that will be used to notify when the blueprint processing finishes',
    )
    operation: Literal['scale']
    add_areas: List[K8sAreaInfo]
    modify_areas: List[K8sAreaInfo]
    del_areas: List[K8sAreaInfo]


