from enum import Enum
from logging import Logger
from typing import List, Optional
from pydantic import Field, field_validator

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.log import create_logger

logger: Logger = create_logger('Vim model')


class VimTypeEnum(str, Enum):
    OPENSTACK = 'openstack'
    PROXMOX = 'proxmox'
    EXTERNAL_REST = 'external_rest'

class ProxmoxPrivilegeEscalationTypeEnum(str, Enum):
    NONE = 'none'
    SUDO_WITHOUT_PASSWORD = 'sudo_without_password'
    #SUDO_WITH_PASSWORD = 'sudo_with_password' TODO not implemented yet

class OpenstackParameters(NFVCLBaseModel):
    region_name: Optional[str] = Field(default="RegionOne")
    project_name: Optional[str] = Field(default="admin")
    user_domain_name: Optional[str] = Field(default="Default")
    project_domain_name: Optional[str] = Field(default="Default")

class ProxmoxParameters(NFVCLBaseModel):
    proxmox_realm: Optional[str] = Field(default="pam")
    proxmox_node: Optional[str] = Field(default=None)
    proxmox_images_volume: Optional[str] = Field(default='local')
    proxmox_vm_volume: Optional[str] = Field(default='local-lvm')
    proxmox_token_name: Optional[str] = Field(default='')
    proxmox_token_value: Optional[str] = Field(default='')
    proxmox_otp_code: Optional[str] = Field(default='')
    proxmox_privilege_escalation: Optional[ProxmoxPrivilegeEscalationTypeEnum] = Field(default=ProxmoxPrivilegeEscalationTypeEnum.NONE)


class VimModel(NFVCLBaseModel):
    """
    """
    class VimConfigModel(NFVCLBaseModel):
        insecure: bool = True
        APIversion: str = 'v3.3'
        use_floating_ip: bool = False

    name: str
    vim_type: VimTypeEnum = VimTypeEnum.OPENSTACK
    vim_url: str
    vim_user: str = 'admin'
    vim_password: str = 'admin'
    vim_timeout: Optional[int] = Field(default=None)
    ssh_keys: Optional[List[str]] = Field(default_factory=list)

    vim_openstack_parameters: Optional[OpenstackParameters] = Field(default=None)
    vim_proxmox_parameters: Optional[ProxmoxParameters] = Field(default=None)

    config: VimConfigModel = Field(default=VimConfigModel())
    networks: List[str] = Field(default_factory=list)
    routers: List[str] = Field(default_factory=list)
    areas: List[int] = Field(default_factory=list)

    def proxmox_parameters(self) -> ProxmoxParameters:
        if self.vim_proxmox_parameters is None:
            self.vim_proxmox_parameters = ProxmoxParameters()
        return self.vim_proxmox_parameters

    def openstack_parameters(self) -> OpenstackParameters:
        if self.vim_openstack_parameters is None:
            self.vim_openstack_parameters = OpenstackParameters()
        return self.vim_openstack_parameters

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, VimModel):
            return self.name == other.name
        return False

    @field_validator("name")
    def validate_lb_pools(cls, name: str) -> str:
        # Removing uppercase
        new_name = name.lower()
        # Replacing - with _
        new_name = new_name.replace("-", "_")

        return new_name

    def add_net(self, net: str):
        """
        Add a network to the VIM
        Args:
            net: the network to be added (the name must be the same on OSM)
        Raises: ValueError if already present or empty name
        """
        if net in self.networks or net == "":
            msg_err = "Network ->{}<- is already present in the VIM ->{}<-".format(net, self.name)
            logger.warning(msg_err)
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
            logger.warning(msg_err)
        else:
            idx = self.networks.index(net_name)
            return self.networks.pop(idx)

    def get_net(self, net_name: str) -> str:
        if net_name not in self.networks:
            msg_err = "Network ->{}<- is NOT in the VIM ->{}<-.".format(net_name, self.name)
            logger.error(msg_err)
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
            logger.warning(msg_err)
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
            logger.warning(msg_err)
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
            logger.warning(msg_err)
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
            logger.warning(msg_err)
        else:
            idx = self.areas.index(area_id)
            return self.areas.pop(idx)

    ## ROUTERS

    def get_router(self, router_name: str) -> str:
        if router_name not in self.routers:
            msg_err = "Router ->{}<- is NOT in the VIM ->{}<-.".format(router_name, self.name)
            logger.error(msg_err)
        else:
            return router_name
