from enum import Enum
from logging import Logger
from typing import List
from pydantic import BaseModel, HttpUrl, Field
from models.k8s.blueprint_k8s_model import VMFlavors
from utils.log import create_logger

logger: Logger = create_logger('Vim model')


class VimTypeEnum(str, Enum):
    openstack: str = 'openstack'


class VimModel(BaseModel):
    class VimConfigModel(BaseModel):
        # class VimAdditionalProperties(BaseModel):
        insecure: bool = True
        APIversion: str = 'v3.3'
        use_floating_ip: bool = False
        # additionalProp1: VimAdditionalProperties

    name: str
    vim_type: VimTypeEnum = 'openstack'
    schema_version: str = '1.3'
    vim_url: HttpUrl
    vim_tenant_name: str = 'admin'
    vim_user: str = 'admin'
    vim_password: str = 'admin'
    config: VimConfigModel = {'additionalProp1': {'insecure': True, 'APIversion': 'v3.3'}}
    networks: List[str] = []
    routers: List[str] = []
    areas: List[int] = []

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, VimModel):
            return self.name == other.name
        return False

    def add_net(self, net: str):
        """
        Add a network to the VIM
        Args:
            net: the network to be added (the name must be the same on OSM)
        Raises: ValueError if already present or empty name
        """
        if net in self.networks or net == "":
            msg_err = "Network ->{}<- is already present in the VIM ->{}<-".format(net, self.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            self.networks.append(net)

    def del_net(self, net_name: str) -> str:
        """
        Remove a network from the VIM
        Args:
            net_name: The network to be removed
        Returns: The name of the net that has been removed
        Raises: ValueError if no network with that name is present

        """
        if net_name not in self.networks:
            msg_err = "Network ->{}<- is NOT in the VIM ->{}<-. Cannot remove.".format(net_name, self.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            idx = self.networks.index(net_name)
            return self.networks.pop(idx)

    def get_net(self, net_name: str) -> str:
        if net_name not in self.networks:
            msg_err = "Network ->{}<- is NOT in the VIM ->{}<-.".format(net_name, self.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            return net_name

    def get_nets(self) -> List[str]:
        return self.networks

    def add_router(self, router: str):
        """
        Add a router to the VIM
        Args:
            router: the router to be added (the name must be the same on OSM)
        Raises: ValueError if already present or empty name
        """
        if router in self.routers or router == "":
            msg_err = "Router ->{}<- is already present in the VIM ->{}<-".format(router, self.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            self.routers.append(router)

    def del_router(self, router_name: str) -> str:
        """
        Remove a router from the VIM
        Args:
            router_name: The router to be removed
        Returns: The name of the router that has been removed
        Raises: ValueError if no router with that name is present

        """
        if router_name not in self.networks:
            msg_err = "Router ->{}<- is NOT in the VIM ->{}<-. Cannot remove.".format(router_name, self.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            idx = self.routers.index(router_name)
            return self.routers.pop(idx)

    def add_area(self, area_id: int):
        """
        Add an area to the VIM
        Args:
            area_id: the area to be added.
        Raises: ValueError if already present or empty name
        """
        if area_id in self.areas or area_id == "":
            msg_err = "Area ->{}<- is already present in the VIM ->{}<-".format(area_id, self.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            self.areas.append(area_id)

    def del_area(self, area_id: int) -> int:
        """
        Remove an area from the VIM
        Args:
            area_id: The area to be removed
        Returns: The area that has been removed
        Raises: ValueError if no router with that name is present
        """
        if area_id not in self.areas:
            msg_err = "Area ->{}<- is NOT present in the VIM ->{}<-. Cannot remove.".format(area_id, self.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            idx = self.areas.index(area_id)
            return self.areas.pop(idx)

    ## ROUTERS

    def get_router(self, router_name: str) -> str:
        if router_name not in self.routers:
            msg_err = "Router ->{}<- is NOT in the VIM ->{}<-.".format(router_name, self.name)
            logger.error(msg_err)
            raise ValueError(msg_err)
        else:
            return router_name


class UpdateVimModel(BaseModel):
    name: str
    networks_to_add: List[str] = Field(
        [],
        description="List of network names declared in the topology to be added to the VIM"
    )
    networks_to_del: List[str] = Field(
        [],
        description="List of network names declared in the topology to be deleted to the VIM"
    )
    routers_to_add: List[str] = Field(
        [],
        description="List of router names declared in the topology to be added to the VIM"
    )
    routers_to_del: List[str] = Field(
        [],
        description="List of router names declared in the topology to be added to the VIM"
    )
    areas_to_add: List[int] = Field(
        [],
        description="List of served area identifiers declared in the topology to be added to the VIM"
    )
    areas_to_del: List[int] = Field(
        [],
        description="List of served area identifiers declared in the topology to be added to the VIM"
    )


class VimLink(BaseModel):
    vld: str
    name: str
    mgt: bool
    port_security_enabled: bool = Field(default=True, alias="port-security-enabled")


class VirtualDeploymentUnit(BaseModel):
    count: int = Field(default=1)
    id: str
    image: str
    vm_flavor: VMFlavors = Field(default=VMFlavors(), alias="vm-flavor")
    interface: List[VimLink] = Field(default=[])
    vim_monitoring: bool = Field(default=True, alias="vim-monitoring")


class VirtualNetworkFunctionDescriptor(BaseModel):
    username: str = Field(default="root")
    password: str
    id: str
    name: str
    vdu: List[VirtualDeploymentUnit] = Field(default=[])
