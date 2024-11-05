import json
import traceback
import typing
from logging import Logger
from multiprocessing import RLock

from nfvcl.models.k8s.common_k8s_model import LBPool
from nfvcl.models.k8s.topology_k8s_model import TopologyK8sModel
from nfvcl.models.network import PduModel, NetworkModel, RouterModel
from nfvcl.models.network.network_models import RouterPortModel, IPv4ReservedRange
from nfvcl.models.prometheus.prometheus_model import PrometheusServerModel
from nfvcl.models.topology import TopologyModel
from nfvcl.models.vim import VimModel, UpdateVimModel
from nfvcl.utils.database import save_topology, delete_topology, get_nfvcl_database
from nfvcl.utils.decorators import obj_multiprocess_lock
from nfvcl.utils.file_utils import remove_files_by_pattern
from nfvcl.utils.ipam import *
from nfvcl.utils.log import create_logger
from nfvcl.utils.redis_utils.event_types import TopologyEventType
from nfvcl.utils.redis_utils.redis_manager import trigger_redis_event
from nfvcl.utils.redis_utils.topic_list import TOPOLOGY_TOPIC
from nfvcl.utils.util import get_nfvcl_config

topology_lock = RLock()

logger: Logger = create_logger('Topology')


class Topology:
    _model: TopologyModel | None

    def __init__(self, topo: Union[dict, None], lock: RLock):
        self.lock = lock
        self._os_terraformer = {}
        if topo:
            if isinstance(topo, TopologyModel):
                self._data = topo.model_dump()
                self._model = topo
            else:
                try:
                    self._model = TopologyModel.model_validate(topo)
                    self._data = self._model.model_dump()
                except Exception:
                    logger.error(traceback.format_exc())
                    raise ValueError("Topology cannot be initialized")

        else:
            msg_err = "Topology information are not existing"
            self._model = None
            logger.warning(msg_err)

    @classmethod
    def from_db(cls, lock: RLock):
        """
        Return the topology from the DB as TopologyModel instance.
        Args:
            lock: the resource lock
        Returns:
            Topology: The instance of the topology from the database
        """
        db = get_nfvcl_database()
        topo = db.find_one_in_collection("topology", {})
        if topo:
            data = TopologyModel.model_validate(topo).model_dump()
        else:
            data = None
        return cls(data, lock)

    def _save_topology(self) -> None:
        """
        Save the content of self._data into the db. Update self._model with current self._data values.
        """
        content = TopologyModel.model_validate(self._data)
        self._model = content
        plain_dict = json.loads(content.model_dump_json())
        save_topology(plain_dict)

    def _save_topology_from_model(self) -> None:
        """
        Save the content of self._model into the db. Update self._data with current self._model values.
        """
        content = self._model
        self._data = content.model_dump()
        plain_dict = json.loads(content.model_dump_json())
        save_topology(plain_dict)

    # **************************** Topology ***********************
    def get(self) -> dict:
        if hasattr(self, '_data'):
            return self._data
        else:
            return {}

    def get_model(self) -> TopologyModel:
        return self._model

    @obj_multiprocess_lock
    def create(self, topo: TopologyModel, terraform: bool = False) -> None:
        logger.debug(f"Creating topology. Terraform: {terraform}")

        if self._model is not None:
            msg_err = 'It is not possible to allocate a new topology, since another one is already declared'
            logger.error(msg_err)
            raise ValueError(msg_err)
        self._model = topo

        # Moving vim in the request into tmp array, in this way, when performing operation to populate vims, a loop is
        # avoided.
        request_vims = self._model.vims
        self._model.vims = []

        for vim in request_vims:
            logger.info('Starting terraforming VIM {}'.format(vim.name))
            self.add_vim(vim, terraform=terraform)

        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_CREATE, data=self._model.model_dump())

    @obj_multiprocess_lock
    def delete(self, terraform: bool = False) -> None:
        logger.debug("Deleting the topology. Terraform: {}".format(terraform))
        if not self._model:
            msg_err = 'Not possible to delete the topology. No topology is currently allocated'
            logger.error(msg_err)
            raise ValueError(msg_err)

        deleted_topology: TopologyModel = self._model.model_copy()

        # Check for terraform is done inside del_vim method
        for vim in self._model.vims:
            try:
                self.del_vim(vim.name, terraform)
            except Exception as exception:
                logger.error(exception)
                raise exception

        self._os_terraformer = {}

        delete_topology()
        self._model = None
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_DELETE, data=self._model.model_dump())

    # **************************** VIMs ****************************

    @obj_multiprocess_lock
    def add_vim(self, vim_model: VimModel, terraform: bool = False) -> None:
        """
        Add a VIM to the topology. IF required, create resources on the real VIM. Onboard the VIM on OSM to be managed by
        it.
        Args:
            vim_model: The VIM to be added in the topology.
            terraform: If resources will be created on the VIM
        """
        # Check if the vim already exists and add it
        self._model.add_vim(vim_model)

        if terraform:
            # For each network, if terraforming, we need to create it in the real VIM
            for vim_net in vim_model.networks:
                logger.debug('Network >{}< is being added to VIM >{}<'.format(vim_net, vim_model.name))
                self._add_vim_net(vim_net, vim_model, terraform=True)
            for vim_router in vim_model.routers:
                logger.debug('Router >{}< is being added to VIM >{}<'.format(vim_router, vim_model.name))
                self.add_vim_router(vim_router, vim_model)

        # Save the topology
        self._save_topology_from_model()

        # If one of the vim_net has floating ip enabled -> enable floating IP
        use_floating_ip: bool = vim_model.config.use_floating_ip
        for vim_net in vim_model.networks:
            use_floating_ip = use_floating_ip or self.check_floating_ips(vim_net)

        vim_dict = vim_model.model_dump(exclude={'networks', 'routers', 'areas'})
        vim_dict['config']['use_floating_ip'] = use_floating_ip

        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_VIM_CREATE, data=self._model.model_dump())

    @obj_multiprocess_lock
    def del_vim(self, vim_name: str, terraform=False):
        # VIM is unique by name
        vim_model = self._model.get_vim(vim_name)

        # If terraform is enabled, then we need to delete also OpenStack resources
        if terraform:
            # remove all networks, ports and routers from topology and from vim
            for router in self._model.routers:
                if router.name in vim_model.routers:
                    self._os_terraformer[vim_model.name].delRouter(router.name)
            for network in self._model.networks:
                if network.name in vim_model.networks:
                    self._os_terraformer[vim_model.name].delNet(network.name)
        # Local deletion
        self._model.del_vim(vim_model.name)
        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_VIM_DEL, data=self._model.model_dump())

    @obj_multiprocess_lock
    def update_vim(self, update_msg: UpdateVimModel, terraform: bool = True):
        """
        Update an existing VIM.
        Args:
            update_msg: The update message containing information to be edited/added. See the model for further info.
            terraform: If new elements has to be created/destroyed on the VIM (openstack,...)
        """
        try:
            vim_model = self._model.get_vim(update_msg.name)
        except ValueError:
            logger.error("VIM to update has not been found, check the topology!")
            return

        # Each network to be added in VIM
        for vim_net in update_msg.networks_to_add:
            logger.debug("Adding net >{}< to vim >{}<".format(vim_net, vim_model.name))
            self._add_vim_net(vim_net, vim_model, terraform=terraform)
        for vim_net in update_msg.networks_to_del:
            logger.debug("Deleting net >{}< from vim {}".format(vim_net, vim_model.name))
            self._del_vim_net(vim_net, vim_model, terraform=terraform)
        for vim_router in update_msg.routers_to_add:
            logger.debug("Adding router >{}< from vim {}".format(vim_router, vim_model.name))
            self.add_vim_router(vim_router, vim_model, terraform=terraform)
        for vim_router in update_msg.routers_to_del:
            logger.debug("Deleting router {} from vim {}".format(vim_router, vim_model.name))
            self.del_vim_router(vim_router, vim_model, terraform=terraform)
        for vim_area in update_msg.areas_to_add:
            logger.debug("Adding area {} to vim {}".format(vim_area, vim_model.name))
            vim_model.add_area(vim_area)
        for vim_area in update_msg.areas_to_del:
            vim_model.del_area(vim_area)

        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_VIM_UPDATE, data=vim_model.model_dump())

    def get_vim_name_from_area_id(self, area: int) -> Union[str, None]:
        """
        Return the FIRST VIM name, given the area
        Args:
            area: the area for witch the VIM is searched.
        Returns:
            The name of the FIRST matching VIM for that area
        """
        return self.get_vim_from_area_id_model(area).name

    def get_vim_from_area_id(self, area: int) -> dict:
        """
        Returns the FIRST VIM given the area id
        Args:
            area: The area id from witch the VIM is obtained.
        Returns:
            The FIRST vim belonging to that area.
        """
        return self._model.get_vim_by_area(area_id=area).model_dump()

    def get_vim_from_area_id_model(self, area: int) -> VimModel:
        """
        Returns the FIRST VIM given the area id
        Args:
            area: The area id from witch the VIM is obtained.
        Returns:
            The FIRST vim belonging to that area.
        """
        return self._model.get_vim_by_area(area_id=area)

    def get_vim_list_from_area_id_model(self, area: int) -> List[VimModel]:
        """
        Returns the list of VIM given the area id
        Args:
            area: The area id from witch the VIM is obtained.
        Returns:
            The list of vim belonging to that area.
        """
        return self._model.get_vim_list_by_area(area_id=area)

    # **************************** Networks *************************
    def get_network(self, net_name: str, vim_name: typing.Optional[str] = None) -> NetworkModel:
        """
        Retrieve a network from the topology and optionally checks that belongs to a VIM.
        Args:
            net_name: The network to be retrieved
            vim_name: The OPTIONAL name of the vim

        Returns:
            The network in dictionary format.
        Raises:
            ValueError if not found
        """
        return self.get_network_model(net_name, vim_name)

    def get_network_model(self, net_name: str, vim_name: typing.Optional[str] = None) -> NetworkModel:
        """
        Retrieve a network from the topology and optionally checks that belongs to a VIM.
        Args:
            net_name: The network to be retrieved
            vim_name: The OPTIONAL name of the vim

        Returns:
            The network.

        Raises:
            ValueError if not found
        """
        # Raise value error if not found
        net_model: NetworkModel = self._model.get_network(net_name)

        # Check that the required vim has the network
        if vim_name:
            vim = self._model.get_vim(vim_name)
            vim.get_net(net_name)  # Raise error if the VIM does not have the network

        return net_model

    def add_network_by_area(self, network: NetworkModel, areas: List[int] = None, terraform: bool = False):
        """
        Add network to the topology and to the VIMs that belong to the area list.

        Args:
            network: the network to be added in the topology

            areas: area ID list used to retrieve the VIMs. The network is then added to every VIM in the list and,
            if terraform is set to true, the net is created on these VIMs.

            terraform: indicate if the network should be created in the VIM
        """
        vims = []
        for a in areas:
            vims.append(self.get_vim_name_from_area_id(a))
            logger.debug("For area {} the following vims have been selected: {}".format(a, vims))
        self.add_network(network, vims, terraform=terraform)

    # !!! Do NOT put obj_multiprocess_lock since it calls the next function that already have it.
    def add_network(self, network: Union[NetworkModel, dict], vim_names_list: Union[list, None] = None,
                    terraform: bool = False):
        """
        Same of add_network_model but accept dict+model.
        """
        # Converting from dict if necessary
        if not isinstance(network, NetworkModel):
            network_model: NetworkModel = NetworkModel.model_validate(network)
        else:
            network_model = network

        self.add_network_model(network_model, vim_names_list, terraform)

    @obj_multiprocess_lock
    def add_network_model(self, network_model: NetworkModel, vim_names_list: Union[list, None] = None,
                          terraform: bool = False) -> NetworkModel:
        """
        Add network to the topology. If required networks are added to VIMs and terraformed (created on the VIM).
        Args:
            network_model: The network to be added in the topology
            vim_names_list: The list of VIMs in witch the network will be added
            terraform: If network has to be created on the VIMs
        Returns:
            The created network
        """
        # It adds a network to the topology
        added_network = self._model.add_network(network_model)

        # Adding the Network to the desired VIMs. If required, the network is created on the VIM
        if vim_names_list:
            for vim_name in vim_names_list:
                vim = self._model.get_vim(vim_name)
                network_name = network_model.name
                self._add_vim_net(network_name, vim, terraform=terraform)

        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_CREATE_NETWORK, data=network_model.model_dump())
        return added_network

    @obj_multiprocess_lock
    def del_network(self, network: Union[NetworkModel, dict], vim_names_list: Union[list, None] = None, terraform: bool = False):
        """
        Delete a network from the topology. Delete it from required VIM list, terraform if required.
        Args:
            network: The network to be removed from the topology
            vim_names_list: The VIMs from witch the network is removed (the nfvcl representation).
            terraform: If the net has to be deleted on the VIM (network is removed from openstack)
        Returns:
            The removed network
        """
        if isinstance(network, dict):
            network = NetworkModel.model_validate(network)

        # For each required VIM, the network is deleted. Otherwise, the net is removed only from the topology
        if vim_names_list:
            for vim_name in vim_names_list:
                vim: VimModel = self._model.get_vim(vim_name)
                self._del_vim_net(network.name, vim, terraform=terraform)

        self._model.del_network(network.name)
        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_DELETE_NETWORK, data=network.model_dump())

    @obj_multiprocess_lock
    def del_network_by_name(self, network_name: str, terraform: bool = False):
        """
        Delete a network from the topology. If terraform option, delete it from every VIM in the topology.
        Args:
            network_name: The network to be removed from the topology
            terraform: If the net has to be deleted on every VIM (network is removed from every connected openstack)
        Returns:
            The removed network
        """
        # If terraform, deleting the net on every VIM in witch is present
        if terraform:
            for vim in self._model.vims:
                if network_name in vim.networks:
                    self._del_vim_net(network_name, vim, terraform=terraform)

        delete_net = self._model.del_network(network_name)
        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_DELETE_NETWORK, data=delete_net.model_dump())

    # **************************** Routers **************************

    def get_router(self, router_name: str):
        """
        Returns the required router
        Args:
            router_name: The router to be retrieved

        Returns:
            The desired router info
        """
        # Looking for the router in the topology
        router: RouterModel = self._model.get_router(router_name)
        return router.model_dump()

    @obj_multiprocess_lock
    def add_router(self, router: RouterModel):
        """
        Add a router to the topology
        Args:
            router: The router to be added to the topology. Must not be already present
        Returns:
            The deleted router
        Raises:
            ValueError if already present
        """
        # Crash if already present
        self._model.add_router(router)
        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_CREATED_ROUTER, data=router.model_dump())

    @obj_multiprocess_lock
    def del_router(self, router_name: str, vim_names_list: list = None):
        """
        Delete a router from the topology and optionally from desired VIMs
        Args:
            router_name: The name of the router to be deleted
            vim_names_list: The list of VIMs from witch the router must be removed.

        Returns:
            The deleted router
        """
        router = self._model.del_router(router_name)

        if vim_names_list:
            for vim_name in vim_names_list:
                vim = self._model.get_vim(vim_name)
                # Throw error if router not found in vim
                vim_router = vim.get_router(router.name)

                vim.del_router(vim_router)

        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_DELETED_ROUTER, data=router.model_dump())

    # **************************** VIM updating **********************

    def _add_vim_net(self, vim_net_name: str, vim: VimModel, terraform: bool = False):
        """
        Add a network to a VIM, if the network already exist on the VIM, it does not need to be terraformed it is just
        added to the topology representation.
        Otherwise, the net is created in the VIM.
        Args:
            vim_net_name: The name of the network
            vim: The target VIM
            terraform: If the network has to be created on the VIM

        Returns:
            The created network if terraformed, None otherwise (even if it is added to the topology but not terraformed)
        """
        # Adding the net, raise ValueError if already present
        vim.add_net(vim_net_name)

        # Checking that the network is present in the topology and getting it
        topo_net = self._model.get_network(network_name=vim_net_name)

        # If terraform we need to create the net on OS
        if terraform:
            logger.info('Network >{}< will be terraformed to VIM >{}<'.format(vim_net_name, vim.name))
            # Creating net
            terraformed_ids = self._os_terraformer[vim.name].createNet(topo_net.model_dump().copy())
            terraformed_ids['vim'] = vim.name

            topo_net.ids.append(terraformed_ids)
            return terraformed_ids
        else:
            return None

    def _del_vim_net(self, vim_net_name: str, vim: VimModel, terraform: bool = False) -> str:
        """
        Remove a Network from the desired VIM representation. If terraform it will delete also on the VIM.
        Args:
            vim_net_name: The net to be removed
            vim: The VIM representation on witch the net is removed
            terraform: If the net is deleted on the VIM

        Returns: the name of deleted network on the vim
        """
        vim_model: VimModel = self._model.get_vim(vim.name)
        removed_net = vim_model.del_net(vim_net_name)

        if terraform:
            if not self._os_terraformer[vim.name].delNet(vim_net_name):
                msg_err = "Cannot remove network >{}< from VIM >{}<".format(vim_net_name, vim.name)
                logger.error(msg_err)
                raise ValueError(msg_err)

        self._save_topology_from_model()
        return removed_net

    def del_vim_router(self, vim_router_name: str, vim: VimModel, terraform: bool = False):
        """
        Delete a router in the VIM structure. If required (terraform) it deletes also on the VIM.
        Args:
            vim_router_name: The router to be removed
            vim: The VIM in witch the router has to be removed
            terraform: If the router has to be deleted on the VIM

        Returns:
            ???
        """
        vim.del_router(vim_router_name)

        if terraform:
            return self._os_terraformer[vim.name].delRouter(vim_router_name)
        else:
            return True

    def add_vim_router(self, vim_router_name: str, vim: VimModel, terraform: bool = False):  # TODO test
        """
        ???
        Args:
            vim_router_name:
            vim: The VIM, BEING PART OF THE TOPOLOGY, to witch the router is associated. If the VIM is not part of the
            topology, when topo is saved, the vim does not persist.
            terraform:
        Returns: ???
        """
        vim.add_router(router=vim_router_name)
        topology_router = self._model.get_router(vim_router_name)

        # Create a copy to be used within os terraformer
        router: RouterModel = topology_router.model_copy()
        router_dict = router.model_dump()

        # Check if the router is connected to an external network
        port: RouterPortModel
        for port in router.ports:
            # A topology external net is indicated by network.external param. Then we take only topology networks that
            # are connected to router port.
            ext_net = next((network for network in
                            self._model.networks if network.name == port.net and network.external), None)
            if ext_net:
                # this is an external router
                ids = next((item for item in ext_net.ids if item['vim'] == vim.name), None)
                # TODO transform in dict and then add this data for os terraformer
                router_dict["external_gateway_info"] = {
                    "network_id": ids['l2net_id'],
                    "enable_snat": True,
                    "external_fixed_ips": [
                        {
                            "ip_address": port.ip_addr if 'ip_addr' in port else
                            ext_net.allocation_pool[0].start,
                            "subnet_id": ids['l3net_id']
                        }
                    ]
                }
            else:
                router_dict['internal_net'].append(port.net)

        if terraform:
            ids = self._os_terraformer[vim.name].createRouter(router_dict)
        else:
            ids = []
        self._save_topology_from_model()
        return ids

    def get_routers_in_net(self, net_name: str) -> List[RouterModel]:
        """
        Returns all router being part of a network (at least one port connected to the network)
        Args:
            net_name: The network
        Returns: Routers (dictionary) that have at leas one port connected to the network
        """
        res = []
        for router in self._model.routers:
            # check if the net is connected to this router
            net_port = next((item for item in router.ports if item.net == net_name), None)
            if net_port is not None:
                res.append(router)
        return res

    def get_routers_in_net_model(self, net_name: str) -> List[RouterModel]:
        """
        Returns all router being part of a network (at least one port connected to the network)
        Args:
            net_name: The network
        Returns: Routers that have at leas one port connected to the network
        """
        res = []
        for router in self._model.routers:
            # check if the net is connected to this router
            net_port = next((item for item in router.ports if item.net == net_name), None)
            if net_port is not None:
                res.append(router)
        return res

    # **************************** Other funcs **********************
    # endpoints are network where VM (and VNFs) can be attached
    def get_network_endpoints(self, vim_name=None) -> List[NetworkModel]:
        """
        Retrieve network endpoints, optionally relative to a vim. Endpoints are network where VM (and VNFs) can be
        attached.
        Args:
            vim_name: The VIM from witch networks endpoint are retrieved, if None net endpoints are the topology
            ones.
        Returns:
            A list containing net endpoints
        """
        if vim_name:
            # Getting the vim net list
            vim_nets: List[NetworkModel] = next((vim.networks for vim in self._model.vims if vim_name == vim.name), [])
            net_names = [net.name for net in vim_nets]
            # Retrieving only network endpoint in the topology that are associated with the desired VIM
            return [net for net in self._model.networks if not net.external and net.name in net_names]
        else:
            return [net for net in self._model.networks if not net.external]

    def check_floating_ips(self, net_name: str) -> bool:
        """
        Check that floating IPs are enabled in the net (SNAT is enabled for the net)
        Args:
            net_name: The net to be checked

        Returns:
            True if floating IPs are supported
        """
        # Network require a floating IP if at least one of the router attached is external
        net_routers: List[RouterModel] = self.get_routers_in_net(net_name)
        for router in net_routers:
            # Check if the NET is connected to this router
            if (router.external_gateway_info and
                "enable_snat" in router.external_gateway_info and
                router.external_gateway_info["enable_snat"] is True):
                return True
        return False

    def reserve_range_lb_pool(self, lb_pool: LBPool, owner: str) -> IPv4ReservedRange:
        """
        Reserve a range in a network of the topology (defined by LBPool). The range has an owner.
        Args:
            lb_pool: the pool to be reserved
            owner: The name of the owner
        Returns:
            The reserved IP range -> {'start': '192.168.0.1', 'end': '192.168.0.100'}
        """
        return self.reserve_range(lb_pool.net_name, lb_pool.range_length, owner)

    @obj_multiprocess_lock
    def reserve_range(self, net_name: str, range_length: int, owner: str, vim_name: typing.Optional[str] = None) \
        -> IPv4ReservedRange:
        """
        Reserve a range in a network of the topology. The range has an owner. The network can be retrieved from a VIM.
        Args:
            net_name: The name of the network in witch the range will be reserved
            range_length: The range length of the reservation
            owner: The owner of the range
            vim_name: The OPTIONAL vim to witch the network is must be part.

        Returns:
            The IP range -> {'start': '192.168.0.1', 'end': '192.168.0.100'}
        """
        net: NetworkModel = self.get_network(net_name, vim_name)

        # Reserved IPs are the reserved ones + IPs already allocated
        reserved_ips = net.allocation_pool + net.reserved_ranges
        ip_range = get_range_in_cidr(net.cidr, reserved_ips, range_length)

        reserved_range = self.set_reserved_ip_range(ip_range, net_name, owner)

        return reserved_range

    def set_reserved_ip_range(self, ip_range: IPv4Pool, net_name: str, owner: str) -> IPv4ReservedRange:
        """
        Set up a reserved ip range for a network of the topology.
        Args:
            ip_range: the range
            net_name: The network on witch the range will be reserved
            owner: The owner (blueprint) of the reservation

        Returns:
            The reserved IP range
        """
        topo_net = self._model.get_network(net_name)  # Throw error in case not found
        if topo_net.external:
            raise ValueError('Network {} is external. Not possible to reserve any IP ranges.'.format(net_name))

        ip_range = IPv4ReservedRange(start=ip_range.start, end=ip_range.end, owner=owner)
        topo_net.add_reserved_range(ip_range)

        self._save_topology_from_model()  # Since we are working on the model
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_CREATE_RANGE_RES, data=ip_range.model_dump())
        return ip_range

    @obj_multiprocess_lock
    def release_ranges(self, owner: str, ip_range: IPv4ReservedRange = None,
                       net_name: str = None) -> IPv4ReservedRange:
        """
        Release a reserved range. It is possible by giving the owner name or the full specification.
        Args:
            owner: The owner of the reservation. Mandatory
            ip_range: Optional IP range, in case there are multiple reservation.
            net_name: Optional network name in witch the reservation is searched.
        Returns:
            The deleted IP range reservation
        """
        removed_range: Union[IPv4ReservedRange, None] = None

        if net_name is None:
            # Iterating over all the networks because no network was given.
            for network in self._model.networks:
                removed_range = network.release_range(owner=owner, ip_range=ip_range)
                if removed_range:
                    break
        else:
            # Looking for the reservation to be removed in the desired network
            network = self._model.get_network(net_name)
            removed_range = network.release_range(owner=owner, ip_range=ip_range)

        if removed_range is None:
            msg_err = f"The range owned by {owner} has NOT been found and removed."
            logger.error(msg_err)
        else:
            self._save_topology_from_model()
            trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_DELETE_RANGE_RES, data=removed_range.model_dump())
            return removed_range

    @obj_multiprocess_lock
    def add_pdu(self, pdu_input: PduModel):
        """
        Add PDU to the topology
        Args:
            pdu_input: The PDU to be added to the topology
        """
        try:
            self._model.add_pdu(pdu_input)

            # Saving changes to the topology
            self._save_topology_from_model()

            trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_CREATE_PDU, data=pdu_input.model_dump())

        except ValueError:
            # Value error is thrown when the PDU already exist
            logger.error(traceback.format_exc())

    @obj_multiprocess_lock
    def upd_pdu(self, pdu_input: PduModel):
        """
        Add PDU to the topology
        Args:
            pdu_input: The PDU to be added to the topology
        """
        self._model.upd_pdu(pdu_input)

        # Saving changes to the topology
        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_CREATE_PDU, data=pdu_input.model_dump())

    @obj_multiprocess_lock
    def del_pdu(self, pdu_name: str):
        """
        Delete a PDU from the topology. De-onboard it from OSM if previously onboarded.
        Args:
            pdu_name: The name of the PDU to be removed from the topology
        """
        pdu = self._model.get_pdu(pdu_name)

        deleted_pdu = self._model.del_pdu(pdu_name)

        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_DELETE_PDU, data=deleted_pdu.model_dump())
        self._save_topology_from_model()

    def get_pdu(self, pdu_name: str) -> PduModel:
        """
        Returns a PDU given the name
        Args:
            pdu_name: The name of the PDU

        Returns: The PDU

        Raises: ValueError if the PDU is not found
        """
        return self._model.get_pdu(pdu_name)

    def get_pdus(self) -> List[PduModel]:
        """
        Returns a list of PDUs
        """
        return self._model.get_pdus()

    def get_k8s_clusters(self) -> List[TopologyK8sModel]:
        """
        Get the k8s cluster list from the topology as List[K8sModel]

        Returns:
            List[TopologyK8sModel]: the k8s cluster list
        """
        return self._model.kubernetes

    def get_k8s_cluster(self, cluster_name: str) -> TopologyK8sModel:
        """
        Get the k8s cluster from the topology

        Returns:
            TopologyK8sModel: the desired k8s cluster

        Raises:
            ValueError if not found.
        """
        return self._model.find_k8s_cluster(cluster_name)

    def get_k8s_cluster_by_area(self, area_id: int) -> TopologyK8sModel:
        """
        Get the first k8s cluster from the topology given the area id.

        Args:

            area_id: the area id in of the cluster to get.

        Returns:

            The FIRST matching k8s cluster or Throw ValueError if NOT found.
        """
        return self._model.find_k8s_cluster_by_area(area_id)

    @obj_multiprocess_lock
    def add_k8scluster(self, data: TopologyK8sModel):
        """
        Add the k8s cluster to the topology. If specified it onboard the cluster on OSM
        Args:
            data: the k8s cluster to be adde
        """
        # Delegate adds operation to the model. Registering the cluster on OSM if requested
        self._model.add_k8s_cluster(data)

        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_CREATE_K8S, data=data.model_dump())

    @obj_multiprocess_lock
    def del_k8scluster(self, cluster_id: str):
        """
        Delete a k8s cluster instance from the k8s cluster list of the topology.

        Args:
            cluster_id: The id (or name) of the cluster to be removed
        """
        k8s_deleted_cluster = self._model.del_k8s_cluster(cluster_id)

        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_DELETE_K8S, data=k8s_deleted_cluster.model_dump())

    @obj_multiprocess_lock
    def update_k8scluster(self, cluster: TopologyK8sModel):
        """
        Update a topology K8s cluster
        Args:
            cluster: The k8s cluster to be added in the topology
        """
        updated_cluster = self._model.upd_k8s_cluster(cluster)

        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_UPDATE_K8S, data=updated_cluster.model_dump())

    @obj_multiprocess_lock
    def add_prometheus_server(self, prom_server: PrometheusServerModel):
        """
        Add prometheus server to the topology. After this operation, it should be possible to configure this instance to
        scrape data from target dynamically from the NFVCL.
        Args:
            prom_server: The server that will be added to the topology
        """
        # Check if there is an instance with the same id
        self._model.add_prometheus_srv(prom_server)
        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_CREATE_PROM_SRV, data=prom_server.model_dump())

    @obj_multiprocess_lock
    def del_prometheus_server(self, prom_srv_id: str, force: bool = False) -> PrometheusServerModel:
        """
        Delete prometheus server from the topology.
        Args:
            prom_srv_id: The ID of the prom server to be removed from the topology
            force: The force removal even if there are configured jobs.
        Returns:
            The deleted instance
        """
        deleted_prom_instance = self._model.del_prometheus_srv(prom_srv_id, force)

        remove_files_by_pattern(get_nfvcl_config().nfvcl.tmp_folder, f"prometheus_{prom_srv_id}*")

        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_DELETE_PROM_SRV, data=deleted_prom_instance.model_dump())
        return deleted_prom_instance

    @obj_multiprocess_lock
    def update_prometheus_server(self, prom_server: PrometheusServerModel):
        """
        Update a Prometheus server instance of the topology
        Args:
            prom_server: The prometheus server to be updated
        """
        updated_instance = self._model.upd_prometheus_srv(prom_server)
        prom_server.update_remote_sd_file()

        self._save_topology_from_model()
        trigger_redis_event(TOPOLOGY_TOPIC, TopologyEventType.TOPO_UPDATE_PROM_SRV, data=updated_instance.model_dump())

    def get_prometheus_server(self, prom_server_id: str) -> PrometheusServerModel:
        """
        Return a specific instance of a prometheus server given the ID from the topology.
        Args:
            prom_server_id: The ID of the instance to be retrieved.

        Returns:
            The prometheus server instace
        """
        prom_instance = self._model.find_prom_srv(prom_server_id)

        return prom_instance

    def get_prometheus_servers_model(self) -> List[PrometheusServerModel]:
        """
        Returns the prometheus server instance model list
        """
        return self._model.prometheus_srv

    def get_prometheus_servers(self) -> dict:
        """
        Returns the prometheus server instance list (dict)
        """
        list_model = self._data['prometheus_srv']
        return list_model


def build_topology() -> Topology:
    """
    Build and returns a topology item.
    Returns:
        A topology object ready to operate on the topology.
    """
    return Topology.from_db(topology_lock)
