from enum import Enum
from ipaddress import IPv4Address
from logging import Logger
from blueprints import BlueprintBase, parse_ansible_output
from models.k8s.k8s_models import K8sPluginName, K8sTemplateFillData
from models.vim.vim_models import VimLink, VirtualDeploymentUnit, VirtualNetworkFunctionDescriptor
from .configurators.k8s_configurator_beta import ConfiguratorK8sBeta
from nfvo import sol006_VNFbuilder, sol006_NSD_builder, get_ns_vld_ip, NbiUtil
from typing import Union, Dict, Optional, List
from models.k8s.blue_k8s_model import K8sBlueprintCreate, K8sBlueprintScale, K8sBlueprintModel, VMFlavors
from utils.k8s import install_plugins_to_cluster, get_k8s_config_from_file_content, get_k8s_cidr_info
from main import nfvcl_config, persistency
from utils.log import create_logger
from .models.blue_k8s_model import LBPool, K8sAreaInfo

db = persistency.DB()
logger: Logger = create_logger('K8s Blue BETA')
nbiUtil = NbiUtil(username=nfvcl_config.osm.username, password=nfvcl_config.osm.password,
                  project=nfvcl_config.osm.project, osm_ip=nfvcl_config.osm.host, osm_port=nfvcl_config.osm.port)


class AreaType(Enum):
    CORE = 1
    AREA = 2


class K8sBeta(BlueprintBase):
    config_model: K8sBlueprintModel

    @classmethod
    def rest_create(cls, msg: K8sBlueprintCreate):
        """
        Defines the creation REST for this blueprint. In particular the type of message to be accepted by the creation
        rest.
        """
        return cls.api_day0_function(msg)

    @classmethod
    def rest_scale(cls, msg: K8sBlueprintScale, blue_id: str):
        """
        Defines scale REST for this blueprint. In particular the type of message to be accepted by the scale APIs.
        """
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def day2_methods(cls):
        """
        Defines the day 2 APIs for this blueprint. In particular the type of message to be accepted by the day 2 APIs,
        and the type of call (PUT).
        """
        cls.api_router.add_api_route("/{blue_id}/scale_new", cls.rest_scale, methods=["PUT"])

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None):
        """
        Constructor of the blueprint.
        It calls the parent constructor to build the data structure, then it fills the config model for this blueprint
        and initialize some values.
        The supported operations define the order of creation operations (init phase) and the ones to be executed during
        scale and other types of operations
        """
        BlueprintBase.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
        logger.info("Creating K8S Blueprint")
        self.supported_operations = {
            'init': [{
                'day0': [{'method': 'bootstrap_day0'}],
                'day2': [{'method': 'init_controller_day2_conf', 'callback': 'get_master_key'},
                         {'method': 'add_worker_day2'},
                         {'method': 'add_worker_area_label', 'callback': 'add_to_topology'},
                         {'method': 'install_plugins'}],
                'dayN': []
            }],
            'scale': [{
                'day0': [{'method': 'add_worker'}],
                'day2': [{'method': 'add_worker_day2'},
                         {'method': 'add_worker_area_label'}],
                'dayN': [{'method': 'del_worker'}]
            }],
            'monitor': [{
                'day0': [],
                'day2': [{'method': 'enable_prometheus'}],
                'dayN': []
            }],
            'log': [{
                'day0': [],
                'day2': [{'method': 'enable_elk'}],
                'dayN': []
            }],
        }
        # !!! Self.to_db() is not only saving the data in the DB, but it fills also the self.config_model variable.
        self.to_db()

        self.config_model.config.nfvo_onboarded = False
        self.primitives = []
        self.vnfd = {'core': [], 'area': []}
        core_area = next((item for item in self.config_model.areas if item.core), None)
        if core_area:
            self.config_model.config.core_area = core_area
        else:
            raise ValueError('Core area not found in the input')

    def bootstrap_day0(self, msg: dict) -> list:
        """
        This is the FIRST M
        Args:
            msg:

        Returns:

        """
        msg_model = K8sBlueprintCreate.parse_obj(msg)
        self.topology_terraform(msg_model)

        # The returned nsd list [] is used to spawn network services, if self.nsd() is empty then no VM, containers are
        # created.
        return self.nsd()

    def topology_terraform(self, k8s_create_model: K8sBlueprintCreate) -> None:
        """
        For each area in witch the cluster will be deployed it checks that a VIM exists and that the data net is present
        in the VIM's networks
        Then if a pool is not already present from the k8s blueprint creation message, it assigns a Load Balancer IP
        address pool to the cluster for each data net.

        Args:
            k8s_create_model: the k8s blueprint creation message
        """
        logger.debug("Blue {} - terraform".format(self.get_id()))
        lb_pool_list: List[LBPool] = []

        for data_net in k8s_create_model.config.network_endpoints.data_nets:
            # lb_pool is the one load balancer pool
            lb_pool: LBPool = data_net.copy()
            logger.debug("Blue {} - checking pool {}".format(self.get_id(), lb_pool.net_name))

            # For every area we need to check that VIM of that area exists and network is listed in that VIM
            for area in k8s_create_model.areas:
                logger.debug("Blue {} - Checking area {}".format(self.get_id(), area.id))
                # check if the VIM exists
                vim = self.topology_get_vim_by_area(area.id)
                if not vim:
                    raise ValueError('Blue {} - no VIMs at area {}'.format(self.get_id(), area.id))
                # Checking if the load-balancing network exists at the VIM
                if lb_pool.net_name not in vim['networks']:
                    raise ValueError('Blue {} - network ->{}<- not available at VIM {}'
                                     .format(self.get_id(), lb_pool.net_name, vim['name']))

            # If the starting IP of this load balancer pool in not present then we generate automatically a range
            if lb_pool.ip_start is None:
                logger.debug("{} retrieving lb IP range".format(self.get_id()))
                range_length = lb_pool.range_length if lb_pool.range_length else 20

                # !!! llb_range is returned as a dictionary
                llb_range = self.topology_reserve_ip_range(lb_pool.dict(), range_length)
                logger.info("Blue {} taking range {}-{} on network {} for lb"
                            .format(self.get_id(), llb_range['start'], llb_range['end'], lb_pool.net_name))
                lb_pool.ip_start = IPv4Address(llb_range['start'])
                lb_pool.ip_end = IPv4Address(llb_range['end'])
            lb_pool_list.append(lb_pool)

        self.config_model.config.network_endpoints.data_nets = lb_pool_list
        logger.info("asd")

    def nsd(self) -> List[str]:
        """
        Build the network service descriptors for K8s service.
        Returns:
            A list of NSD to be deployed
        """
        logger.info("Creating K8s Network Service Descriptors")
        nsd_names = [self.controller_nsd()]

        area: K8sAreaInfo
        # For each area we can have multiple workers (depending on workers replicas)
        for area in self.config_model.areas:
            logger.info(
                "Blue {} - Creating K8s Worker Service Descriptors on area {}".format(self.get_id(), area.id))
            for replica_id in range(area.workers_replica):
                nsd_names.append(self.worker_nsd(area, replica_id))

        logger.info("NSDs created")
        return nsd_names

    def controller_nsd(self) -> str:
        """
        Build the k8s controller Network Service Descriptor

        Returns:
            the name of the NSD
        """
        logger.info("Building controller NSD")

        param = {
            'name': '{}_K8S_C'.format(self.get_id()),
            'id': '{}_K8S_C'.format(self.get_id()),
            'type': 'master'
        }
        # Maps the 'mgt' to the vim_net
        vim_net_mapping = [
            {'vld': 'mgt', 'vim_net': self.config_model.config.network_endpoints.mgt, "mgt": True}
        ]

        # For each data network that should be connected to the worker it creates a map between vld net name and the vim
        # net name.
        for pool in self.config_model.config.network_endpoints.data_nets:
            if pool.net_name != vim_net_mapping[0]['vim_net']:
                vim_net_mapping.append(
                    {'vld': 'data_{}'.format(pool.net_name), 'vim_net': pool.net_name, "mgt": False}
                )

        # Create the VNFD for the core area (the K8s controller)
        created_vnfd = [self.set_vnfd(AreaType.CORE, vld=vim_net_mapping)]  # sol006_NSD_builder expect a list

        n_obj = sol006_NSD_builder(
            created_vnfd, self.get_vim_name(self.config_model.config.core_area.dict()), param, vim_net_mapping)

        # Append to the NSDs the just created NSD for the controller
        self.nsd_.append(n_obj.get_nsd())
        return param['name']

    def worker_nsd(self, area: K8sAreaInfo, replica_id: int) -> str:
        logger.info("Blue {} - building worker NSD for replica {} at area {}"
                    .format(self.get_id(), replica_id, area.id))
        vim_net_mapping = [
            {'vld': 'mgt', 'vim_net': self.config_model.config.network_endpoints.mgt, "mgt": True}
        ]

        # For each data network that should be connected to the worker it creates a map between vld net name and the vim
        # net name.
        for pool in self.config_model.config.network_endpoints.data_nets:
            if pool.net_name != vim_net_mapping[0]['vim_net']:
                vim_net_mapping.append(
                    {'vld': 'data_{}'.format(pool.net_name), 'vim_net': pool.net_name, "mgt": False}
                )

        # The default values are already filled in self.config_model.config.worker_flavors
        vm_flavor = self.config_model.config.worker_flavors.copy()
        # If flavor is given in the k8s creation request then use these values
        if area.worker_flavor_override:
            vm_flavor = area.worker_flavor_override

        # Setting the vnf descriptor
        created_vnfd = [self.set_vnfd(AreaType.AREA, area.id, vld=vim_net_mapping, vm_flavor_request=vm_flavor,
                                      replica=replica_id)]

        param = {
            'name': '{}_K8S_A{}_W{}'.format(self.get_id(), area.id, replica_id),
            'id': '{}_K8S_A{}_W{}'.format(self.get_id(), area.id, replica_id),
            'type': 'worker'
        }

        n_obj = sol006_NSD_builder(
            created_vnfd, self.get_vim_name(area.id), param, vim_net_mapping)

        n_ = n_obj.get_nsd()
        n_['area'] = area.id
        n_['replica_id'] = replica_id
        self.nsd_.append(n_)
        return param['name']

    def set_vnfd(self, area_type: AreaType, area_id: Optional[int] = None, vld: Optional[list] = None,
                 vm_flavor_request: Optional[VMFlavors] = None, replica: int = 0) -> None:
        """
        Set the Virtual network function descriptor for an area (both core area and normal area).

        Args:
            area_type: the area type
            area_id: the optional area id (for not core areas)
            vld: optional virtual link descriptors (for not core areas)
            vm_flavor_request: optional VM flavors to override default ones.
            replica: the replica number of the worker

        Returns:
            the created VNFD
        """
        logger.debug("Setting VNFd for {}".format(area_type))

        # VM default flavors for k8s, if not overwritten
        vm_flavor = VMFlavors()
        vm_flavor.vcpu_count = 4
        vm_flavor.memory_mb = 6144
        vm_flavor.storage_gb = 8
        # They can be overwritten on demand
        if vm_flavor_request is not None:
            vm_flavor = vm_flavor_request

        # VDU is common but the interfaces are changing soo we will update in the specific case
        if area_id:
            vdu_id = "A{}_R{}".format(area_id, replica)  # A1 = area 1, A32 = area 32
        else:
            vdu_id = "AC"
        vdu = VirtualDeploymentUnit(id=vdu_id, image='ubuntu2204-March-23')
        vdu.vm_flavor = vm_flavor

        created_vnfd = None
        if area_type == AreaType.AREA:
            created_vnfd = self.set_vnfd_area(vdu, area_id, vld, replica=replica)
        if area_type == AreaType.CORE:
            created_vnfd = self.set_vnfd_core(vdu, vld)

        return created_vnfd

    def set_vnfd_core(self, vdu: VirtualDeploymentUnit, vld: List) -> dict:
        """
        Set the Virtual network function descriptor for the core area
        Args:
            vdu: the virtual deployment unit on witch the VM for the core is based on
            vld: The list of virtual link descriptors to be attached at the controller

        Returns:
            the created VNFD
        """
        # Core has only mgt interface
        # Worker has multiple interfaces differently from the controller (just mgt)
        interfaces = []
        intf_index = 3  # starting from ens3
        for l_ in vld:
            interfaces.append(VimLink.parse_obj({"vld": l_["vld"], "name": "ens{}".format(intf_index),
                                                 "mgt": l_["mgt"], "port-security-enabled": False}))
            intf_index += 1
        vdu.interface = interfaces

        vnfd = VirtualNetworkFunctionDescriptor.parse_obj({
            'password': 'root',
            'id': '{}_AC'.format(self.get_id()),
            'name': '{}_AC'.format(self.get_id()),
        })
        vnfd.vdu = [vdu]
        complete_vnfd = sol006_VNFbuilder(self.nbiutil, self.db, vnfd.dict(by_alias=True),
                                          charm_name='helmflexvnfm', cloud_init=True)
        id_vnfd = {'id': 'vnfd', 'name': complete_vnfd.get_id(),
                   'vl':  [i.dict() for i in interfaces]}
        self.vnfd['core'].append(id_vnfd)
        self.to_db()

        return id_vnfd

    def set_vnfd_area(self, vdu: VirtualDeploymentUnit, area_id: Optional[int] = None, vld: Optional[list] = None,
                      replica: int = 0) -> dict:
        if area_id is None:
            raise ValueError("Area is None in set Vnfd")
        if vld is None:
            raise ValueError("VLDs for worker vnf are None in setVnfd function")

        # Worker has multiple interfaces differently from the controller (just mgt)
        interfaces = []
        intf_index = 3  # starting from ens3
        for l_ in vld:
            interfaces.append(VimLink.parse_obj({"vld": l_["vld"], "name": "ens{}".format(intf_index),
                                                 "mgt": l_["mgt"], "port-security-enabled": False}))
            intf_index += 1

        vdu.interface = interfaces
        vnfd = VirtualNetworkFunctionDescriptor.parse_obj({
            'password': 'root',
            'id': '{}_A{}_R{}'.format(self.get_id(), area_id, replica),
            'name': '{}_A{}_R{}'.format(self.get_id(), area_id, replica),
        })
        vnfd.vdu = [vdu]

        complete_vnfd = sol006_VNFbuilder(self.nbiutil, self.db, vnfd.dict(by_alias=True), charm_name='helmflexvnfm',
                                          cloud_init=True)

        area_vnfd = {'area_id': area_id, 'id': 'vnfd', 'name': complete_vnfd.get_id(),
                     'vl': [i.dict() for i in interfaces]}
        self.vnfd['area'].append(area_vnfd)
        self.to_db()

        return area_vnfd

    def init_controller_day2_conf(self, msg):
        """
        After the controller VM is ready this method configure the controller (install and configure k8s)

        Args:
            msg: The received message. IT is not used but necessary otherwise crash.

        Returns:
            the configuration dump of the controller.
        """
        logger.debug("Triggering Day2 Config for K8S blueprint " + str(self.get_id()))
        res = []
        # Looks for the NSD of the master (or k8s controller)
        master_nsd = next(item for item in self.nsd_ if item['type'] == 'master')
        # Create a configurator for the k8s controller and dumps the actions to be executed into conf_dump
        conf_dump = ConfiguratorK8sBeta(master_nsd['descr']['nsd']['nsd'][0]['id'], 1, self.get_id(), self.config_model,
                                        role='master', step=1).dump()
        # saving the id of the action because we need to post process its output
        # self.action_to_check.append(conf_[0]['param_value']['action_id'])
        self.action_to_check.append(conf_dump[0]['primitive_data']['primitive_params']['config-content'])
        res += conf_dump
        logger.debug("K8s master configuration built")

        self.to_db()
        return res

    def get_master_key(self, msg) -> None:
        """
        Set the local master key and the master credentials in this object. Once ansible of the controller has been
        executed, it contains an instruction to save the master key and credentials in the primitive output.
        It is then sufficient to look for that data in the ansible playbook output

        Args:
            msg: The callback msg containing the ansible outputs
        """
        for primitive in msg:
            # Check that everything is ok
            if primitive['result']['charm_status'] != 'completed':
                raise ValueError('in k8s blue -> get_master_key callback charm_status is not completed')

            logger.debug(primitive['primitive'])
            playbook_name = \
                primitive['primitive']['primitive_data']['primitive_params']['config-content']['playbooks'][0]['name']
            # action_id = primitive['result']['details']['detailed-status']['output']
            action_id = primitive['primitive']['primitive_data']['primitive_params']['config-content']['action_id']

            action_output = db.findone_DB('action_output', {'action_id': action_id})
            logger.debug('**** retrieved action_output {}'.format(action_output['action_id']))

            # retrieve data from action output
            self.config_model.config.master_key_add_worker = parse_ansible_output(action_output, playbook_name,
                                                                                  'worker join key', 'msg')
            self.config_model.config.master_credentials = parse_ansible_output(action_output, playbook_name,
                                                                               'k8s credentials', 'msg')['stdout']
        self.to_db()

    def add_worker(self, msg: K8sBlueprintScale) -> List[str]:
        """
        This method is used to handle scale operations.
        It can add new area with relative number of workers or add workers to existing areas
        It is **NOT** support worker removal.
        """
        logger.info("Adding worker to K8S blueprint " + str(self.get_id()))
        nsd_names = []
        for area in msg.add_areas:
            logger.info("Blue {} - activating new area {}".format(self.get_id(), area.id))
            # check if area is already existing in self.conf, or it is a new area
            checked_area = next((item for item in self.config_model.areas if item.id == area.id), None)
            if checked_area:
                raise ValueError("Blue {} - area {} already exists!".format(self.get_id(), area.id))
            for index in range(1, area.workers_replica+1):
                logger.info("Blue {} - adding worker {} on area {}".format(self.get_id(), index, area.id))
                nsd_names.append(self.worker_nsd(area, index))
            self.config_model.areas.append(area)

        for area in msg.modify_areas:
            # check if area is already existing in self.conf, or it is a new area
            checked_area = next((item for item in self.config_model.areas if item.id == area.id), None)
            if checked_area:
                # area already existing, checking replicas
                if checked_area.workers_replica < area.workers_replica:
                    for index in range(checked_area.workers_replica + 1, area.workers_replica):
                        logger.info("Blue {} - adding worker {} on area {}".format(self.get_id(), index, area.id))
                        nsd_names.append(self.worker_nsd(area, index))
                elif checked_area.workers_replica == area.workers_replica:
                    logger.warning("Blue {} - no workers to be added on area {}".format(self.get_id(), area.id))
                else:
                    logger.warning("Blue {} - workers to be deleted on area {}!!!".format(self.get_id(), area.id))
                    # FIXME: how to deal with dayN?

        self.to_db()
        return nsd_names

    def add_worker_day2(self, msg):
        """
        Build the configuration to be executed on the worker nodes!
        This method should work for both day0 and day2.
        For each area we can have multiple replicas.
        """
        res = []

        if type(msg) is dict:
            # If the request is coming from initial config, msg is a dict (depends on NFVCL code).
            # But since the message is the same on witch the object is build we can use the data in config model that is
            # the same.
            areas = self.config_model.areas
        elif type(msg) is K8sBlueprintScale:
            # Otherwise, for example in scaling operation, we receive an object of type K8sBlueprintScale
            msg_ojb: K8sBlueprintScale = msg
            areas = msg_ojb.add_areas
        else:
            logger.warning("Message type non recognized {}".format(msg))
            areas = []

        for area in areas:
            for n in self.nsd_:
                # For each network service descriptor in the area we check that the NS is a 'worker'
                if n['type'] == 'worker' and n['area'] == area.id:
                    # We build a configurator that will give us back the instructions to be executed via ansible on the
                    # worker
                    res += ConfiguratorK8sBeta(
                        n['descr']['nsd']['nsd'][0]['id'],
                        1,
                        self.get_id(),
                        self.config_model,
                        role='worker',
                        master_key=self.config_model.config.master_key_add_worker
                    ).dump()

        logger.debug("K8s worker configuration built")
        self.to_db()
        # The resources to be executed are returned and then executed by the caller on the workers
        return res

    def add_worker_area_label(self, msg):
        """
        Add the labels on k8s worker nodes. The label must be added though the controller since is a k8s instruction.

        Args:
            msg: if this method is called in the init phase, the message is the creation request, then we retrieve the
            workers to be labeled from the blue config model. If it is called by a scaling operation we can get the
            workers to be labeled from this argument (K8sBlueprintScale).
        """
        logger.debug("Blue {} - Triggering Day2 Add area label to workers ".format(self.get_id()))
        if type(msg) is dict:
            # If the request is coming from initial config, msg is a dict (depends on NFVCL code).
            # But since the message is the same on witch the object is build we can use the data in config model that is
            # the same.
            areas = self.config_model.areas
        elif type(msg) is K8sBlueprintScale:
            # Otherwise, for example in scaling operation, we receive an object of type K8sBlueprintScale
            msg_ojb: K8sBlueprintScale = msg
            areas = msg_ojb.add_areas
        else:
            logger.warning("Message type non recognized {}".format(msg))
            areas = []

        areas_to_label = [item.id for item in areas]
        workers_to_label = []
        for area_id in areas_to_label:
            # Looks for the workers to be labeled in the k8s cluster
            conf_area = next((item for item in self.config_model.areas if item.id == area_id), None)
            if not conf_area:
                raise ValueError('Blue {} - configuration area {} not found'.format(self.get_id(), area_id))

            # looking for workers' vdu names (they are the names seen by the K8s master)
            vm_names = []
            for n in self.nsd_:
                if n['type'] == 'worker' and n['area'] == area_id:
                    vnfi = self.nbiutil.get_vnfi_list(n['nsi_id'])[0]
                    vm_names.append(vnfi['vdur'][0]['name'])
            workers_to_label.append({'area': area_id, 'vm_names': vm_names})

        configurator = ConfiguratorK8sBeta(
            next(item['descr']['nsd']['nsd'][0]['id'] for item in self.nsd_ if item['type'] == 'master'),
            1,
            self.get_id(),
            self.config_model,
            role='master',
            step=2
        )
        configurator.add_worker_label(workers_to_label)
        return configurator.dump()

    def add_to_topology(self, callback_msg):
        """
        Once the K8s cluster is ready it is added to the topology.
        In this way it is possible to use the cluster to deploy services on top of K8s through the NFVCL.
        """
        for primitive in callback_msg:
            if primitive['result']['charm_status'] != 'completed':
                raise ValueError('in k8s blue -> add_to_topology callback charm_status is not completed')

        k8s_data = {
            'name': self.get_id(),
            'provided_by': 'blueprint',
            'blueprint_ref': self.get_id(),
            'k8s_version': self.conf['config']['version'],
            'credentials': self.conf['config']['master_credentials'],
            'vim_account': self.get_vim(self.conf['config']['core_area']),
            'vim_name': self.get_vim(self.conf['config']['core_area'])['name'],
            'networks': [item['net_name'] for item in self.conf['config']['network_endpoints']['data_nets']],
            'areas': [item['id'] for item in self.conf['areas']],
            'nfvo_onboarded': False
        }
        self.topology_add_k8scluster(k8s_data)

    def install_plugins(self, msg: dict):
        """
        Day 2 operation. Install k8s plugins after the cluster has been initialized.
        Suppose that there are NO plugin installed.

        Args:
            msg: The received message. IT is not used but necessary otherwise crash.

        Returns:
            Empty primitive list such that caller does not crash
        """
        client_config = get_k8s_config_from_file_content(self.conf['config']['master_credentials'])
        # Build plugin list
        plug_list: List[K8sPluginName] = []

        if self.conf['config']['cni'] == 'flannel':
            plug_list.append(K8sPluginName.FLANNEL)
        elif self.conf['config']['cni'] == 'calico':
            plug_list.append(K8sPluginName.CALICO)
        plug_list.append(K8sPluginName.METALLB)
        plug_list.append(K8sPluginName.OPEN_EBS)
        plug_list.append(K8sPluginName.METRIC_SERVER)

        # Get the pool list for metal load balancer
        pool_list = self.config_model.config.network_endpoints.data_nets
        # Get the k8s pod network cidr
        pod_network_cidr = get_k8s_cidr_info(client_config)
        # create additional data for plugins (lbpool and cidr)
        add_data = K8sTemplateFillData(pod_network_cidr=pod_network_cidr, lb_pools=pool_list)

        install_plugins_to_cluster(kube_client_config=client_config, plugins_to_install=plug_list,
                                   template_fill_data=add_data, cluster_id=self.id)

        # Returning empty primitives to avoid error.
        return []

    def del_worker(self, msg: K8sBlueprintScale) -> List[str]:
        """
        Remove a worker from this k8s blueprint instance
        Args:
            msg: K8sBlueprintScale object containing the workers to be removed

        Returns:
            A list of Network Service Identifiers to be deleted (from OSM?)
        """
        logger.info("Deleting worker from K8S blueprint " + str(self.get_id()))
        nsi_to_delete = []
        for area in msg.del_areas:
            checked_area = next((item for item in self.config_model.areas if item.id == area.id), None)
            if not checked_area:
                raise ValueError("Blue {} - area {} not found".format(self.get_id(), area.id))

            logger.debug("Blue {} - deleting K8s workers on area {}".format(self.get_id(), area.id))
            # find nsi to be deleted
            for n in self.nsd_:
                if n['type'] == 'worker':
                    if n['area'] == area.id:
                        logger.debug("Worker on area {} has nsi_id: {}".format(area.id, n['nsi_id']))
                        nsi_to_delete.append(n['nsi_id'])
            # removing items from conf
            # Note: this should be probably done, after deletion confirmation from the nfvo
            self.config_model.areas = [item for item in self.config_model.areas if item.id != area.id]

        for area in msg.modify_areas:
            # check if area is already existing in self.conf, or it is a new area
            checked_area = next((item for item in self.config_model.areas if item.id == area.id), None)
            if checked_area:
                # area already existing, checking replicas
                if checked_area.workers_replica > area.workers_replica:
                    nsi_ids = [item for item in self.nsd_ if item['area'] == area.id]
                    logger.info("Blue {} - from area {} removing service instances: {}"
                                .format(self.get_id(), area.id, nsi_ids))
                    nsi_to_delete.extend(nsi_ids[0:(checked_area['workers_replica'] - area.id)])
                    checked_area.workers_replica = area.workers_replica
                elif checked_area.workers_replica == area.workers_replica:
                    logger.warning("Blue {} - no workers to be deleted on area {}".format(self.get_id(), area.id))

        return nsi_to_delete

    # ---------- Override --------------------------------------------------

    def to_db(self):
        """
        @override
        This method is used to save the model inside the self.conf variable.
        This workaround is needed because otherwise the vyos model is not saved, and the self.conf variable is a dict.
        """
        val = getattr(self, 'config_model', None)
        # If this is the first time the config model will be 'None' and we need to load the data from self.conf (that is
        # coming from the database)

        if val:
            # We update self.conf that is SAVED into the DB, differently from self.config_model.
            # In this way the model will be saved into the DB
            self.conf = self.config_model.dict()
        else:
            # If the blueprint instance is loaded for the first time, then the model is empty, and we can parse the
            # dictionary into the model
            self.config_model = K8sBlueprintModel.parse_obj(self.conf)
        # To save the data (in particular the self.conf variable) we call the super method
        super(K8sBeta, self).to_db()

    def _destroy(self):
        """
        Called when the blueprint is destroyed.
        """

        # If onboarded, the k8s cluster is removed from OSM.
        logger.info("Destroying")
        if self.config_model.config.nfvo_onboarded:
            nbiUtil.delete_k8s_cluster(self.get_id())

        # The k8s repo is removed from OSM
        nbiUtil.delete_k8s_repo(self.get_id())

        # K8s cluster is removed from the topology
        self.topology_del_k8scluster()

        # Release the reserved IP addresses for the Load Balancer (see
        self.topology_release_ip_range()

    def get_ip(self) -> None:
        """
        Retrieve information about VM instances IPs.

        VMs are spawned by OSM and OpenStack, we do not decide IPs to be assigned to VMs.
        For this reason it is necessary to obtain this data after they have been created.
        """
        logger.debug('getting IP addresses from vnf instances')

        for n in self.nsd_:
            if n['type'] == 'master':
                # Retrieve the complete virtual link descriptors for the only interface of the k8s controller!
                vlds = get_ns_vld_ip(n['nsi_id'], ["mgt"])
                self.config_model.config.controller_ip = vlds["mgt"][0]['ip']
            if n['type'] == 'worker':
                # Looking for the area corresponding to the actual NSD
                target_area = next(area for area in self.config_model.areas if area.id == n['area'])
                if not target_area.worker_data_int:
                    target_area.worker_data_int = {}
                # links
                vld_names = ["mgt"]
                for pool in self.config_model.config.network_endpoints.data_nets:
                    # If the net is not the management one
                    if pool.net_name != self.config_model.config.network_endpoints.mgt:
                        # Then append the net to virtual link descriptors
                        vld_names.append('data_{}'.format(pool.net_name))

                # Retrieve the complete virtual link descriptors for every link of the network service (k8s WORKER)!
                vlds = get_ns_vld_ip(n['nsi_id'], vld_names)

                # need to add interfaces names such that we can assign the correct ip later on!
                target_area.worker_mgt_int = vlds["mgt"][0]
                target_area.worker_data_int[n['replica_id']] = [{"net": item, "ip": vlds[item][0]} for item in
                                                                vlds]
            self.to_db()