from enum import Enum
from logging import Logger
from typing import List, Optional
from pydantic import Field, field_validator, field_serializer

from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.network import PduInterface
from nfvcl.utils.log import create_logger

logger: Logger = create_logger('Vim model')


class VimTypeEnum(str, Enum):
    OPENSTACK: str = 'openstack'
    PROXMOX: str = 'proxmox'


class VimModel(NFVCLBaseModel):
    """
    Represents the model to be sent at OSM for VIM management

    References:
        https://osm.etsi.org/docs/user-guide/latest/04-vim-setup.html?highlight=floating#openstack
    """

    class VimConfigModel(NFVCLBaseModel):
        # https://osm.etsi.org/docs/user-guide/latest/04-vim-setup.html?highlight=floating#configuration-options-reference
        insecure: bool = True
        APIversion: str = 'v3.3'
        use_floating_ip: bool = False

    name: str
    vim_type: VimTypeEnum = VimTypeEnum.OPENSTACK
    schema_version: str = '1.3'
    vim_url: str
    vim_tenant_name: str = 'admin'
    vim_user: str = 'admin'
    vim_password: str = 'admin'
    ssh_keys: Optional[List[str]] = Field(default_factory=list)
    vim_proxmox_realm: Optional[str] = Field(default='pam')
    vim_proxmox_storage_id: Optional[str] = Field(default='local')
    vim_proxmox_storage_volume: Optional[str] = Field(default='local-lvm')
    osm_onboard: Optional[bool] = Field(default=False)
    config: VimConfigModel = Field(default=VimConfigModel())
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

    @field_validator("name")
    @classmethod
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


class UpdateVimModel(NFVCLBaseModel):
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


class VimNetMap(NFVCLBaseModel):
    vld: str
    name: str
    vim_net: str
    mgt: bool
    k8s_cluster_net: str = Field(alias='k8s-cluster-net', default='data_net')
    ip_address: Optional[str] = Field(default=None, alias='ip-address', description="Ip address of the Network mapping")

    @classmethod
    def build_vnm(cls, vld, name, vim_net, mgt, k8s_cluster_net='data_net'):
        return VimNetMap(vld=vld, name=name, vim_net=vim_net, mgt=mgt, k8s_cluster_net=k8s_cluster_net)


class VimLink(NFVCLBaseModel):
    vld: str
    name: str
    mgt: bool
    intf_type: Optional[str] = Field(default=None)
    port_security_enabled: bool = Field(default=True, alias="port-security-enabled")

    @classmethod
    def build_vim_link(self, net_map: VimNetMap, intf_type: str = None, port_security_enabled: bool = True):
        return VimLink(vld=net_map.vld, name=net_map.name, mgt=net_map.mgt, intf_type=intf_type, port_security_enabled=port_security_enabled)


class VMFlavors(NFVCLBaseModel):
    memory_mb: str = Field(default="8192", alias='memory-mb', description="Should be a multiple of 1024")
    storage_gb: str = Field(default="32", alias='storage-gb')
    vcpu_count: str = Field(default="4", alias='vcpu-count')

    @field_validator('memory_mb', 'storage_gb', 'vcpu_count', mode='before')
    @classmethod
    def validate_field(cls, input_val) -> str:
        to_ret: str
        if isinstance(input_val, str):
            return input_val
        elif isinstance(input_val, int):
            return str(input_val)
        else:
            raise ValueError("VMFlavors -> input value is not a string neither an int.")


class VirtualDeploymentUnit(NFVCLBaseModel):
    count: int = Field(default=1)
    id: str
    image: str
    vm_flavor: VMFlavors = Field(default=VMFlavors(), alias="vm-flavor")
    interface: List[VimLink] = Field(default=[])
    vim_monitoring: bool = Field(default=True, alias="vim-monitoring")

    @classmethod
    def build_vdu(cls, vdu_id, vdu_image, vdu_data_int_list: List[str], vdu_flavor: VMFlavors = VMFlavors()):
        """

        Args:
            vdu_id: The ID of the vdu
            vdu_image: The name of the image used in openstack (origin)
            vdu_data_int_list: A list of data network NAMES
            vdu_flavor: Flavor to be assigned to this vdu.

        Returns:

        """
        interfaces: List[VimLink] = []

        # Starting from ens3. Management interface is ens3
        interfaces.append(VimLink.model_validate({
            "vld": "mgt",
            "name": "ens3",
            "mgt": True,
            "port-security-enabled": False
        }))

        intf_index = 4  # starting from ens4
        for net_name in vdu_data_int_list:
            interfaces.append(VimLink.model_validate({
                "vld": f'data_{net_name}',
                "name": f"ens{intf_index}",
                "mgt": False,
                "port-security-enabled": False
            }))
            intf_index += 1

        return VirtualDeploymentUnit(id=vdu_id, image=vdu_image, vm_flavor=vdu_flavor, interface=interfaces)


class PhysicalDeploymentUnit(NFVCLBaseModel):
    count: int = Field(default=1)
    id: str
    interface: List[PduInterface] = Field(default=[])  # Should correspond to PduInterface in net models

    @classmethod
    def build_pdu(cls, count: int, id: str, interface: List[PduInterface]):
        return PhysicalDeploymentUnit(count=count, id=id, interface=interface)


class KubeDeploymentUnit(NFVCLBaseModel):
    name: str
    helm_chart: str = Field(alias='helm-chart')
    interface: Optional[List[VimNetMap]] = Field(default=None)

    @classmethod
    def build_kdu(cls, name, helm_chart, interface: Optional[List[VimNetMap]] = None):
        """

        Args:
            name: KDU name
            helm_chart: Helm chart, must be on a repository added on OSM
            interface: TODO ?

        Returns:

        """
        return KubeDeploymentUnit(name=name, helm_chart=helm_chart, interface=interface)


class VirtualNetworkFunctionDescriptor(NFVCLBaseModel):
    id: str
    name: str
    username: str = Field(default="root")
    password: str = Field(default="root")
    become_password: Optional[str] = Field(default="root")
    vdu: Optional[List[VirtualDeploymentUnit]] = Field(default=[])
    pdu: Optional[List[PhysicalDeploymentUnit]] = Field(default=[])
    kdu: Optional[List[KubeDeploymentUnit]] = Field(default=[])
    mgmt_cp: Optional[str] = Field(default=None, description="VLD of mgt interface")
    cloud_init: Optional[bool] = Field(default=None)

    @classmethod
    def build_vnfd(cls,
                   vnf_id: str,
                   vnf_username: str = "root",
                   vnf_passwd: str = "root",
                   cloud_init: bool = False,
                   vdu_list: List[VirtualDeploymentUnit] = None,
                   pdu_list: List[PhysicalDeploymentUnit] = None,
                   kdu_list: List[KubeDeploymentUnit] = None,
                   vnf_become_passwd: Optional[str] = None):
        vnfd = VirtualNetworkFunctionDescriptor.model_validate({
            'id': vnf_id,
            'name': vnf_id,
            'password': vnf_passwd,
            'username': vnf_username,
        })
        vnfd.become_password = vnf_become_passwd
        vnfd.vdu = vdu_list if vdu_list is not None else []
        vnfd.pdu = pdu_list if pdu_list is not None else []
        vnfd.kdu = kdu_list if kdu_list is not None else []
        vnfd.cloud_init = cloud_init

        return vnfd

    @field_serializer('vdu', 'kdu', 'pdu')
    @classmethod
    def serialize_list(self, list_to_ser: List, _info):
        """
        If the list is empty return None such that when the model is serialized -> Empty list are not included in the
        dump of the model.
        WARNING: use exclude_none option when serializing the model:
            model.model_dump(by_alias=True, exclude_none=True)

        Args:
            list_to_ser: The list to be serialized
            _info:

        Returns:
            None if the list is None or empty. The list content otherwise.
        """
        if list_to_ser is None:
            return None
        elif isinstance(list_to_ser, list):
            if len(list_to_ser) > 0:
                return list_to_ser
            else:
                return None
        else:
            return None
