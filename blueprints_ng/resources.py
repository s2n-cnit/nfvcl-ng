import abc
from pathlib import Path
from typing import Optional, List, Dict, Union

from kubernetes.client import V1ServiceList
from pydantic import Field
from typing_extensions import Literal

from models.base_model import NFVCLBaseModel
from models.k8s.k8s_objects import K8sService, K8sServicePort, K8sServiceType


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

    def get_name_k8s_format(self):
        """
        Returns the name of the node given by k8s to the node
        """
        return self.name.lower().replace('_','-')


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
    name: Optional[str] = Field(default=None, description="The name of the flavor, if specified NFVCL will try to use that flavor, if not found it will try to create new one with following specs.")
    vcpu_count: str = Field(default="4")
    memory_mb: str = Field(default="8192", description="Should be a multiple of 1024")
    storage_gb: str = Field(default="32")
    vcpu_type: Optional[str] = Field(default="host")


class VmResourceNetworkInterfaceAddress(NFVCLBaseModel):
    """
    Represent a VM network interface.

    Attributes:
        interface_name (str): The name of the network interface inside the VM
        mac (str): The MAC address of the interface inside the VM
        ip (str): The IP address of the interface inside the VM
        cidr (str): The IP network attached to the interface
    """
    interface_name: str = Field(default="")
    mac: str = Field()
    ip: str = Field()
    cidr: str = Field()

    def get_prefix(self) -> str:
        """
        Retrieve the prefix of the network attached to the interface
        Returns:
            The prefix of the network attached to the interface (8,16,24, ...)
        """
        return self.cidr.split('/')[-1]

    def get_ip_prefix(self) -> str:
        """
        Retrieve the IP with the prefix of the network attached to the interface
        """
        return f"{self.ip}/{self.get_prefix()}"


class VmResourceNetworkInterface(NFVCLBaseModel):
    """

    Attributes:
        fixed (VmResourceNetworkInterfaceAddress): The IP address of the network interface
        floating (VmResourceNetworkInterfaceAddress): The floating IP assigned to the interface
    """
    fixed: VmResourceNetworkInterfaceAddress = Field()
    floating: Optional[VmResourceNetworkInterfaceAddress] = Field(default=None)


class NetResource(ResourceDeployable):
    cidr: str = Field()


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
        network_interfaces (Dict[str, List[VmResourceNetworkInterface]]): list of network interfaces attached to the VM indexed by vim network name.
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
    require_port_security_disabled: Optional[bool] = Field(default=False) # TODO remove optional

    # Potrebbe mettersi la data di creazione
    created: bool = Field(default=False)
    access_ip: Optional[str] = Field(default=None)
    network_interfaces: Dict[str, List[VmResourceNetworkInterface]] = Field(default_factory=dict)
    # TODO accesa, spenta, in inizializzazione..., cambiare tipo con enum
    state: Optional[str] = Field(default=None)

    def get_management_interface(self) -> VmResourceNetworkInterface:
        """
        Retrieves the management network interface
        """
        return self.network_interfaces[self.management_network][0]

    def get_additional_interfaces(self) -> List[VmResourceNetworkInterface]:
        """
        Retrieves the additional network interfaces
        """
        additional_interfaces_list = []
        for key in self.additional_networks:
            additional_interfaces_list.extend(self.network_interfaces[key])
        return additional_interfaces_list

    def get_network_interface_by_name(self, name: str) -> VmResourceNetworkInterface | None:
        """
        Search for a network interface with the given name in the VM.
        Args:
            name: The name of the interface.

        Returns:
            If found, returns the interface instance, otherwise None
        """
        for net_interface_list in self.network_interfaces.values():
            for net_interface in net_interface_list:
                if net_interface.fixed.interface_name == name:
                    return net_interface
        return None

    def check_if_network_connected_by_name(self, network_name: str) -> bool:
        """
        Check if the network is connected to the VM
        Args:
            network_name: The name of the network (on the VIM)

        Returns:
            True if it connected, False otherwise
        """
        if network_name in self.network_interfaces.keys():
            return True

    def check_if_network_connected_by_cidr(self, cidr: str) -> bool:
        """
        Check if the network is connected to the VM
        Args:
            cidr: The CIDR of the network (on the VIM)

        Returns:
            True if it connected, False otherwise
        """
        for net_interface_list in self.network_interfaces.values():
            for net_interface in net_interface_list:
                if net_interface.fixed.cidr == cidr:
                    return True
        return False


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

    created: bool = Field(default=False)
    services: Optional[Dict[str, K8sService]] = Field(default=None)

    def set_services_from_k8s_api(self, k8s_services: V1ServiceList):
        self.services = {}

        for k8s_service in k8s_services.items:
            external_ips: List[str] = []
            ports: List[K8sServicePort] = []

            for port in k8s_service.spec.ports:
                ports.append(K8sServicePort(name=port.name, port=port.port, protocol=port.protocol, targetPort=port.target_port))

            if k8s_service.spec.type == K8sServiceType.LoadBalancer.value:
                for external_ip in k8s_service.status.load_balancer.ingress:
                    external_ips.append(external_ip.ip)

            service = K8sService(
                type=k8s_service.spec.type,
                name=k8s_service.metadata.name,
                cluster_ip=k8s_service.spec.cluster_ip,
                external_ip=external_ips,
                ports=ports
            )

            self.services[service.name] = service

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
