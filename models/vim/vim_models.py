from enum import Enum
from logging import Logger
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, field_serializer
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
    vim_url: str
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
    # TODO aggregate with PduInterface??? They are very similar models
    vld: str
    name: str
    mgt: bool
    intf_type: Optional[str] = Field(default=None)
    port_security_enabled: bool = Field(default=True, alias="port-security-enabled")


class VimNetMap(BaseModel):
    vld: str
    name: str
    vim_net: str
    mgt: bool
    k8s_cluster_net: str = Field(alias='k8s-cluster-net', default='data_net')


class VMFlavors(BaseModel):
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


class VirtualDeploymentUnit(BaseModel):
    count: int = Field(default=1)
    id: str
    image: str
    vm_flavor: VMFlavors = Field(default=VMFlavors(), alias="vm-flavor")
    interface: List[VimLink] = Field(default=[])
    vim_monitoring: bool = Field(default=True, alias="vim-monitoring")

    @classmethod
    def build_vdu(cls, vdu_id, vdu_image, vdu_data_int_list: List[str], vdu_flavor):
        """

        Args:
            vdu_id: The ID of the vdu
            vdu_image: The name of the image used in openstack (origin)
            vdu_mgt_int: The name of the management interface
            vdu_data_int_list: A list of data network NAMES
            vdu_flavor: Flavor to be assigned to this vdu.

        Returns:

        """
        if vdu_flavor is not None:
            vm_flavor = vdu_flavor
        else:
            vm_flavor: VMFlavors = VMFlavors()
            vm_flavor.vcpu_count = '4'
            vm_flavor.memory_mb = '6144'
            vm_flavor.storage_gb = '8'

        interfaces = []
        # Starting from ens3. Management interface is ens3
        interfaces.append(VimLink.model_validate({"vld": "mgt", "name": "ens3",
                                                  "mgt": True, "port-security-enabled": False}))
        intf_index = 4  # starting from ens4
        for net_name in vdu_data_int_list:
            interfaces.append(VimLink.model_validate({"vld": f'data_{net_name}', "name": f"ens{intf_index}",
                                                      "mgt": False, "port-security-enabled": False}))
            intf_index += 1

        vdu = VirtualDeploymentUnit(id=vdu_id, image=vdu_image)
        vdu.vm_flavor = vm_flavor
        vdu.interface = interfaces

        return vdu


class PDUDeploymentUnit(BaseModel):
    count: int = Field(default=1)
    id: str
    interface: dict  # Should correspond to PduInterface in net models


class KubeDeploymentUnit(BaseModel):
    name: str
    helm_chart: str = Field(alias='helm-chart')
    interface: Optional[VimNetMap] = Field(default=None)


class VirtualNetworkFunctionDescriptor(BaseModel):
    id: str
    name: str
    username: str = Field(default="root")
    password: str
    vdu: Optional[List[VirtualDeploymentUnit]] = Field(default=[])
    pdu: Optional[List[PDUDeploymentUnit]] = Field(default=[])
    kdu: Optional[List[KubeDeploymentUnit]] = Field(default=[])
    mgmt_cp: Optional[str] = Field(default=None, description="VLD of mgt interface")
    cloud_init: Optional[bool] = Field(default=None)

    @classmethod
    def build_vnfd(cls, vnf_id: str, vnf_passwd: str, cloud_init: bool, vnf_username: str = None,
                   vdu_list: List[VirtualDeploymentUnit] = None,
                   pdu_list: List[PDUDeploymentUnit] = None,
                   kdu_list: List[KubeDeploymentUnit] = None):
        vnfd = VirtualNetworkFunctionDescriptor.model_validate({
            'id': vnf_id,
            'name': vnf_id,
            'password': vnf_passwd,
            'username': vnf_username if vnf_username is not None else "root",
        })
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







