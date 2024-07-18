from abc import abstractmethod
from typing import Generic, TypeVar, Optional, Dict, Tuple, final

from pydantic import Field

from nfvcl.blueprints_ng.lcm.blueprint_type_manager import day2_function
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g import Generic5GBlueprintNG, Generic5GBlueprintNGState
from nfvcl.blueprints_ng.resources import HelmChartResource
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint_ng.core5g.common import Create5gModel
from nfvcl.models.blueprint_ng.g5.core import NF5GType, NetworkFunctionScaling
from nfvcl.models.http_models import HttpRequestType
from nfvcl.models.k8s.k8s_objects import K8sService, K8sDeployment
from nfvcl.utils.k8s import get_k8s_config_from_file_content
from nfvcl.utils.k8s.kube_api_utils import k8s_scale_k8s_deployment


class K8s5GNF(NFVCLBaseModel):
    type: NF5GType = Field()
    deployment: K8sDeployment = Field()
    service: Optional[K8sService] = Field(default=None)

class Generic5GK8sBlueprintNGState(Generic5GBlueprintNGState):
    k8s_network_functions: Dict[NF5GType, K8s5GNF] = Field(default_factory=dict)
    core_helm_chart: Optional[HelmChartResource] = Field(default=None)

StateTypeVar5GK8s = TypeVar("StateTypeVar5GK8s", bound=Generic5GK8sBlueprintNGState)
CreateConfigTypeVar5GK8s = TypeVar("CreateConfigTypeVar5GK8s")


class Generic5GK8sBlueprintNG(Generic5GBlueprintNG[Generic5GK8sBlueprintNGState, Create5gModel], Generic[StateTypeVar5GK8s, CreateConfigTypeVar5GK8s]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GK8sBlueprintNGState] = StateTypeVar5GK8s):
        super().__init__(blueprint_id, state_type)

    @property
    def state(self) -> StateTypeVar5GK8s:
        return super().state

    @abstractmethod
    def network_functions_dictionary(self) -> Dict[NF5GType, Tuple[str, str]]:
        pass

    @final
    def update_k8s_network_functions(self):
        """
        Return a dictionary with the name of the deployment and service for each 5g network function
        Examples:
              NF5GType.AMF: ("amf-deployment", "amf-service")
        """
        for nftype, ttuple in self.network_functions_dictionary().items():
            k8s5gnf = K8s5GNF(
                type=nftype,
                deployment=self.state.core_helm_chart.deployments[ttuple[0]],
                service=self.state.core_helm_chart.services[ttuple[1]] if ttuple[1] is not None else None
            )
            self.state.k8s_network_functions[nftype] = k8s5gnf

    @final
    def get_amf_ip(self) -> str:
        return self.state.k8s_network_functions[NF5GType.AMF].service.external_ip[0]

    @day2_function("/scale_nf", [HttpRequestType.PUT])
    def day2_scale_nf(self, nf_scaling: NetworkFunctionScaling):
        """
        Scale a 5G network function replica number of the blueprint
        """
        self.logger.info(f"Scaling {nf_scaling.nf} to {nf_scaling.replica_count} replicas")

        k8s_config = get_k8s_config_from_file_content(self.provider.get_k8s_provider(list(filter(lambda x: x.core == True, self.state.current_config.areas))[0].id).k8s_cluster.credentials)
        k8s_scale_k8s_deployment(
            k8s_config,
            namespace=self.state.core_helm_chart.namespace.lower(),
            deployment_name=self.state.k8s_network_functions[nf_scaling.nf].deployment.name,
            replica_num=nf_scaling.replica_count
        )

        self.logger.success(f"Scaled {nf_scaling.nf} to {nf_scaling.replica_count} replicas")
