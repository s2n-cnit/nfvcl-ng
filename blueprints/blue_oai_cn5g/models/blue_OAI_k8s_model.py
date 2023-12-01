from typing import *
from pydantic import Field

from models.base_model import NFVCLBaseModel
from models.k8s.k8s_objects import K8sService


class OAIAreaModel(NFVCLBaseModel):
    id: int
    config: Optional[Dict[str, Any]] = Field(
        None,
        description='parameters for the day2 configurator of the Blueprint istance'
    )


class OAIBlueCreateModel(NFVCLBaseModel):
    type: Literal["OpenAirInterface_K8s"]

    config: Optional[Dict[str, Any]] = Field(
        None,
        description='parameters for the day2 configurator of the Blueprint istance'

    )

    areas: List[Dict[str, Any]] = Field(
        None,
        description='parameters for the day2 configuration of the Blueprint istance'
    )


class OAIModelServices(NFVCLBaseModel):
    amf: K8sService = Field(alias="oai-amf-svc")
    ausf: K8sService = Field(alias="oai-ausf-svc")
    nrf: K8sService = Field(alias="oai-nrf-svc")
    nssf: K8sService = Field(alias="oai-nssf-svc")
    smf: K8sService = Field(alias="oai-smf-svc")
    udm: K8sService = Field(alias="oai-udm-svc")
    udr: K8sService = Field(alias="oai-udr-svc")
    mysql: K8sService = Field()

class OAIModel(OAIBlueCreateModel):
    core_services: Optional[OAIModelServices] = Field(default=None)
