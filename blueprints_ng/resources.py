from typing import Optional, List, Any, Dict

from pydantic import Field
from typing_extensions import Literal

from models.base_model import NFVCLBaseModel
from models.k8s.k8s_objects import K8sService


class Resource(NFVCLBaseModel):
    id: Optional[str] = Field(default=None)
    type: Literal['Resource'] = "Resource"

    def set_context(self, context):
        self._context = context

    def get_context(self):
        return self._context


class ResourceDeployable(Resource):
    """
    Represents a VM, Helm Chart or PDU
    """
    type: Literal['ResourceDeployable'] = "ResourceDeployable"
    area: str = Field()
    name: str = Field()


class ResourceConfiguration(Resource):
    """
    Represents a configuration for a Resource
    """
    type: Literal['ResourceConfiguration'] = "ResourceConfiguration"
    pass


class VmResourceImage(NFVCLBaseModel):
    """
    Represents a VM Image

    Attributes:
        name (str): The name of the VM image.
        url (str, optional): The URL from witch the image is downloaded if necessary.
    """
    name: str = Field()
    url: Optional[str] = Field(default=None)


class VmResourceFlavor(NFVCLBaseModel):
    memory_mb: str = Field(default="8192", alias='memory-mb', description="Should be a multiple of 1024")
    storage_gb: str = Field(default="32", alias='storage-gb')
    vcpu_count: str = Field(default="4", alias='vcpu-count')


class VmResource(ResourceDeployable):
    """
    Represent a VM Resource to BE instantiated

    Attributes:
        id (str): The id of the VM Resource
        name (str): The name of the VM
        image (VmResourceImage): The image of the VM
        username (str): The username of the VM
        password (str): The password of the VM
        become_password (str): The password to be used in the VM to get admin power
        management_network (str): name of the management network attached to VM (like OS network)
        additional_networks (List[str]): name list of network attached to VM (like OS network)
        network_interfaces (List[Any]): list of network interfaces attached to the VM that includes IP, MAC, port sec, ...
        state (str): running, stopped, initializated,
    """
    image: VmResourceImage = Field()
    flavor: VmResourceFlavor = Field()
    username: str = Field()
    password: str = Field()
    become_password: Optional[str] = Field(default=None)
    management_network: str = Field()
    additional_networks: List[str] = Field(default=[])

    # Potrebbe mettersi la data di creazione
    created: bool = Field(default=False)
    # TODO il tipo deve essere la rappresentazione dell'interfaccia di OS, con IP, mac, nome, port sec, gateway ...
    network_interfaces: Optional[Dict[str, Any]] = Field(default=None)
    # TODO accesa, spenta, in inizializzazione..., cambiare tipo con enum
    state: Optional[str] = Field(default=None)


class VmResourceConfiguration(ResourceConfiguration):
    vm_resource: VmResource = Field()


class VmResourceAnsibleConfiguration(VmResourceConfiguration):

    def dump_playbook(self) -> str:
        print("Esegue dump ansible playbook....")
        return "[[DUMPED PLAYBOOK]]"

    def build_configuration(self, configuration_values: Any):
        print("Costruisco ansible playbook....")


class VmResourceNativeConfiguration(VmResourceConfiguration):
    def run_code(self):
        print("Esegue codice...")


class HelmChartResource(ResourceDeployable):
    chart: str = Field()
    repo: Optional[str] = Field(default=None)
    namespace: str = Field()
    additional_params: Dict[str, Any] = Field()

    created: bool = Field(default=False)
    created_services: Optional[List[K8sService]] = Field(default=None)


class K8SResourceConfiguration(ResourceConfiguration):
    def __init__(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        super().__init__()
        self.helm_chart_resource = helm_chart_resource
        self.values = values
