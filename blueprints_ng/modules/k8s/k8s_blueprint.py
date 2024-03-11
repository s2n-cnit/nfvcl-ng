from typing import Optional, List

from models.k8s.common_k8s_model import Cni
from starlette.requests import Request
from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.modules.k8s.config.day0_configurator import VmK8sDay0Configurator
from models.blueprint_ng.k8s.k8s_rest_models import K8sCreateModel, K8sAreaDeployment
from blueprints_ng.resources import VmResource, VmResourceImage
from pydantic import Field
from blueprints_ng.blueprint_ng import BlueprintNGState, BlueprintNG

K8S_BLUE_TYPE = "k8s"
BASE_IMAGE_MASTER = "ubuntu2204"
BASE_IMAGE_WORKER = "ubuntu2204"


class K8sBlueprintNGState(BlueprintNGState):
    """

    """
    # version: K8sVersion = Field(default=K8sVersion.V1_28) # CRASH
    # cni: Cni = Field(default=Cni.flannel) # CRASH

    pod_network_cidr: str = Field(default="10.254.0.0/16", description='K8s Pod network IPv4 cidr to init the cluster')
    progressive_worker_number: int = 0

    vm_master: Optional[VmResource] = Field(default=None)
    vm_master_configurator: Optional[VmK8sDay0Configurator] = Field(default=None)

    vm_workers: List[VmResource] = []

    master_key_add_worker: str = Field(default="", description="The master key to be used by a worker to join the k8s cluster")
    master_credentials: str = Field(default="", description="The certificate of the admin, to allow k8s administration")

@declare_blue_type(K8S_BLUE_TYPE)
class K8sBlueprint(BlueprintNG[K8sBlueprintNGState, K8sCreateModel]):
    def __init__(self, blueprint_id: str, provider_type: type[BlueprintNGProviderInterface], state_type: type[BlueprintNGState] = K8sBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, provider_type, state_type)

    def create(self, create_model: K8sCreateModel):
        super().create(create_model)
        self.logger.info(f"Starting creation of K8s blueprint")

        area: K8sAreaDeployment
        for area in create_model.areas:
            if area.is_master_area:
                # Defining Master node. Should be executed only once
                self.state.vm_master = VmResource(
                    area=area.area_id,
                    name=f"{self.id}_VM_K8S_C",
                    image=VmResourceImage(name=BASE_IMAGE_MASTER),
                    flavor=create_model.master_flavors,
                    username="ubuntu",
                    password="ubuntu",
                    management_network=area.mgmt_net,
                    additional_networks=[area.service_net]
                )
                # Registering master node
                self.register_resource(self.state.vm_master)
                # Creating the VM
                self.provider.create_vm(self.state.vm_master)
            for worker_replica_num in range(0,area.worker_replicas):
                # Workers of area X
                self.state.progressive_worker_number += 1
                vm = VmResource(
                    area=area.area_id,
                    name=f"{self.id}_VM_W_{self.state.progressive_worker_number}",
                    image=VmResourceImage(name=BASE_IMAGE_WORKER),
                    flavor=area.worker_flavors,
                    username="ubuntu",
                    password="ubuntu",
                    management_network=area.mgmt_net,
                    additional_networks=[area.service_net]
                )
                self.state.vm_workers.append(vm)
                # Registering master node
                self.register_resource(vm)
                # Creating the VM
                self.provider.create_vm(vm)

    @classmethod
    def rest_create(cls, msg: K8sCreateModel, request: Request):
        """
        This is needed for FastAPI to work, don't write code here, just changed the msg type to the correct one
        """
        return cls.api_day0_function(msg, request)

