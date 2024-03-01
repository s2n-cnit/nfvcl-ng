import abc
from pathlib import Path
from typing import Optional, List, Dict, Union

from pydantic import Field
from typing_extensions import Literal

from models.base_model import NFVCLBaseModel
from models.k8s.k8s_objects import K8sService


class Resource(NFVCLBaseModel):
    id: Optional[str] = Field(default=None)
    type: Literal['Resource'] = "Resource"


class ResourceDeployable(Resource):
    """
    Represents a VM, Helm Chart or PDU
    """
    type: Literal['ResourceDeployable'] = "ResourceDeployable"
    area: int = Field()
    name: str = Field()


class ResourceConfiguration(Resource):
    """
    Represents a configuration for a Resource
    """
    type: Literal['ResourceConfiguration'] = "ResourceConfiguration"


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


class VmResourceNetworkInterfaceAddress(NFVCLBaseModel):
    mac: str = Field()
    ip: str = Field()
    cidr: str = Field()

    def get_prefix(self) -> str:
        return self.cidr.split('/')[-1]


class VmResourceNetworkInterface(NFVCLBaseModel):
    fixed: VmResourceNetworkInterfaceAddress = Field()
    floating: Optional[VmResourceNetworkInterfaceAddress] = Field(default=None)


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
        network_interfaces (Dict[str, VmResourceNetworkInterface]): list of network interfaces attached to the VM indexed by vim network name.
        state (str): running, stopped, initializated,
    """
    image: VmResourceImage = Field()
    flavor: VmResourceFlavor = Field()
    username: str = Field()
    password: str = Field()
    become_password: Optional[str] = Field(default=None)
    management_network: str = Field()
    additional_networks: List[str] = Field(default=[])
    require_floating_ip: bool = Field(default=False)

    # Potrebbe mettersi la data di creazione
    created: bool = Field(default=False)
    access_ip: Optional[str] = Field(default=None)
    network_interfaces: Dict[str, VmResourceNetworkInterface] = Field(default_factory=dict)
    # TODO accesa, spenta, in inizializzazione..., cambiare tipo con enum
    state: Optional[str] = Field(default=None)


class VmResourceConfiguration(ResourceConfiguration):
    vm_resource: VmResource = Field()


class VmResourceAnsibleConfiguration(VmResourceConfiguration):
    @abc.abstractmethod
    def dump_playbook(self) -> str:
        pass


class VmResourceNativeConfiguration(VmResourceConfiguration):
    @abc.abstractmethod
    def run_code(self):
        pass


class HelmChartResource(ResourceDeployable):
    chart: str = Field()
    chart_as_path: bool = Field(default=False)
    repo: Optional[str] = Field(default=None)
    version: Optional[str] = Field(default=None)
    namespace: str = Field()
    # additional_params: Dict[str, Any] = Field()

    created: bool = Field(default=False)
    created_services: Optional[List[K8sService]] = Field(default=None)

    def get_chart_converted(self) -> Union[str, Path]:
        if self.chart_as_path:
            return Path(self.chart)
        else:
            return self.chart


class HardwareResource(Resource):
    ip: str = Field()
    username: str = Field()
    password: str = Field()
    become_password: Optional[str] = Field(default=None)


class HardwareResourceConfiguration(ResourceConfiguration):
    hardware_resource: HardwareResource = Field()


class HardwareResourceAnsibleConfiguration(HardwareResourceConfiguration):
    @abc.abstractmethod
    def dump_playbook(self) -> str:
        pass
