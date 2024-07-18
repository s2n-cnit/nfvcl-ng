from abc import abstractmethod
from enum import Enum
from typing import Generic, TypeVar, Optional, Dict, Tuple, final

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g import Generic5GBlueprintNG, Generic5GBlueprintNGState
from nfvcl.blueprints_ng.resources import HelmChartResource
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint_ng.core5g.common import Create5gModel
from nfvcl.models.k8s.k8s_objects import K8sService, K8sDeployment


class NF5GType(str, Enum):
    AMF = 'AMF'
    SMF = 'SMF'
    NSSF = 'NSSF'
    NEF = 'NEF'
    NRF = 'NRF'
    PCF = 'PCF'
    UDM = 'UDM'
    UDR = 'UDR'
    AF = 'AF'
    AUSF = 'AUSF'

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

