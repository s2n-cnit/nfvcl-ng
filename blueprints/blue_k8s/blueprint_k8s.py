import re
from enum import Enum
from ipaddress import IPv4Address
from logging import Logger
from typing import Union, Dict, Optional, List
from blueprints import parse_ansible_output
from main import persistency
from models.blueprint.blueprint_base_model import BlueVNFD
from models.blueprint.common import BluePrometheus
from models.blueprint.rest_blue import BlueGetDataModel
from models.k8s.blueprint_k8s_model import K8sBlueprintCreate, K8sBlueprintScale, K8sBlueprintModel, \
    K8sNsdInterfaceDesc
from models.k8s.blueprint_k8s_model import LBPool, K8sAreaInfo
from models.k8s.plugin_k8s_model import K8sTemplateFillData, K8sPluginName
from models.prometheus.prometheus_model import PrometheusTargetModel
from models.vim.vim_models import VirtualDeploymentUnit, VirtualNetworkFunctionDescriptor, VimModel, VMFlavors, \
    VimNetMap
from models.virtual_link_desc import VirtLinkDescr
from nfvo import NbiUtil
from nfvo.nsd_manager_beta import Sol006NSDBuilderBeta
from nfvo.osm_nbi_util import get_osm_nbi_utils
from nfvo.vnf_manager_beta import Sol006VnfdBuilderBeta
from nfvo.nsd_manager_beta import get_ns_vld_model
from topology.topology import Topology, build_topology
from utils.k8s import install_plugins_to_cluster, get_k8s_config_from_file_content, get_k8s_cidr_info
from utils.log import create_logger
from .configurators.k8s_configurator import ConfiguratorK8sBeta
from ..blueprint_beta import BlueprintBaseBeta

db = persistency.DB()
logger: Logger = create_logger('K8s Blue BETA')
nbiUtil: NbiUtil = get_osm_nbi_utils()


class AreaType(Enum):
    CORE = 1
    AREA = 2


WORKERS_FLAVOR: VMFlavors = VMFlavors(vcpu_count='4', memory_mb='8192', storage_gb='32')
CONTROLLER_FLAVOR: VMFlavors = VMFlavors(vcpu_count='4', memory_mb='4096', storage_gb='16')
VDU_IMAGE = 'ubuntu2204'
DEFAULT_USR = 'root'
DEFAULT_PASSWD = 'root'


class K8sBlue(BlueprintBaseBeta):
    k8s_model: K8sBlueprintModel

    def pre_initialization_checks(self) -> bool:
        return True

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
        Allow to scale up or down the K8S cluster. It is possible to manage nodes belonging to a certain K8s cluster.
        """
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def enable_prom(cls, msg: BluePrometheus, blue_id: str):
        """
        Install and configure a node exporter on each node belonging to the K8s cluster of the specified blueprint.
        """
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def disable_prom(cls, msg: BluePrometheus, blue_id: str):
        """
        Install and configure a node exporter on each node belonging to the K8s cluster of the specified blueprint.
        """
        return cls.api_day2_function(msg, blue_id)

    @classmethod
    def day2_methods(cls):
        """
        Defines the day 2 APIs for this blueprint. In particular the type of message to be accepted by the day 2 APIs,
        and the type of call (PUT).
        """
        cls.api_router.add_api_route("/{blue_id}/scale_new", cls.rest_scale, methods=["PUT"])
        cls.api_router.add_api_route("/{blue_id}/enable_prom", cls.enable_prom, methods=["PUT"])
        cls.api_router.add_api_route("/{blue_id}/disable_prom", cls.disable_prom, methods=["PUT"])

    def __init__(self, conf: dict, id_: str, data: Union[Dict, None] = None):
        """
        Constructor of the blueprint.
        It calls the parent constructor to build the data structure, then it fills the config model for this blueprint
        and initializes some values.
        The supported operations define the order of creation operations (init phase) and the ones to be executed during
        scale and other types of operations
        """
        BlueprintBaseBeta.__init__(self, conf, id_, data=data, nbiutil=nbiUtil, db=db)
        logger.info("Creating K8S Blueprint")
        self.base_model.supported_operations = {
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
                'day2': [{'method': 'prom_pre_checks'},
                         {'method': 'enable_node_exporter'},
                         {'method': 'enable_scraping'}],
                'dayN': []
            }],
            'disable_monitor': [{
                'day0': [],
                'day2': [],
                'dayN': [{'method': 'disable_scraping'}]
            }],
            'log': [{
                'day0': [],
                'day2': [{'method': 'enable_elk'}],
                'dayN': []
            }],
        }
        # DO NOT remove -> model initialization.
        self.k8s_model = K8sBlueprintModel.model_validate(self.base_model.conf)
        # Avoid putting self.db

    def bootstrap_day0(self, msg: dict) -> list:
        """
        This is the FIRST function called on day0
        Args:
            msg: K8sBlueprintCreate, the message used to create the k8s cluster.

        Returns:
            a list of created NSD.
        """
        core_area = next((item for item in self.k8s_model.areas if item.core), None)
        if core_area:
            self.k8s_model.config.core_area = core_area
        else:
            raise ValueError('Core area not found in the input')

        msg_model = K8sBlueprintCreate.model_validate(msg)
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
            lb_pool: LBPool = data_net.model_copy()
            logger.debug("Blue {} - checking pool {}".format(self.get_id(), lb_pool.net_name))

            # For every area we need to check that VIM of that area exists and network is listed in that VIM
            for area in k8s_create_model.areas:
                logger.debug("Blue {} - Checking area {}".format(self.get_id(), area.id))
                # Check if the VIM exists and retrieve it
                vim: VimModel = self.get_topology().get_vim_from_area_id_model(area.id)
                # Checking if the load-balancing network exists at the VIM
                if lb_pool.net_name not in vim.networks:
                    raise ValueError('Blue {} - network ->{}<- not available at VIM {}'
                                     .format(self.get_id(), lb_pool.net_name, vim.name))

            # If the starting IP of this LOAD BALANCER pool in not present then we generate automatically a range
            if lb_pool.ip_start is None:
                logger.debug("{} retrieving lb IP range".format(self.get_id()))
                if not lb_pool.range_length:
                    lb_pool.range_length = 20

                load_bal_topo_res_range = self.get_topology().reserve_range_lb_pool(lb_pool, self.get_id())
                logger.info("Blue {} taking range {}-{} on network {} for LOAD BALANCER".format(self.get_id(),
                                                                                                load_bal_topo_res_range.start,
                                                                                                load_bal_topo_res_range.end,
                                                                                                lb_pool.net_name))
                # Building IPv4Addresses to validate. Then saving string because obj cannot be serialized.
                lb_pool.ip_start = IPv4Address(load_bal_topo_res_range.start).exploded
                lb_pool.ip_end = IPv4Address(load_bal_topo_res_range.end).exploded
            lb_pool_list.append(lb_pool)

        self.k8s_model.config.network_endpoints.data_nets = lb_pool_list
        self.to_db()
        logger.info("asd")

    def nsd(self) -> List[str]:
        """
        Build the network service descriptors for K8s service.
        Returns:
            A list of NSD to be deployed
        """

        nsd_names = []  # For the controller

        area: K8sAreaInfo
        # For each area we can have multiple workers (depending on workers replicas)
        for area in self.k8s_model.areas:
            if area.core:
                logger.info("{} - Creating K8s Controller NSD on area {}".format(self.get_id(), area.id))
                nsd_names.append(self.set_nsd(is_controller=True, area=area))
            logger.info("{} - Creating K8s Worker NSD on area {}".format(self.get_id(), area.id))
            for replica_id in range(area.workers_replica):
                nsd_names.append(self.set_nsd(False, area, replica_id))

        logger.info("NSDs created")
        return nsd_names

    def set_nsd(self, is_controller: bool, area: K8sAreaInfo = None, replica_id: int = None) -> str:
        """
        Build the Network Service descriptor for a NS of the K8s Blueprint.
        For this blueprint
        Args:
            is_controller: indicates if the NS is going to be built for the controller.
            area: The area in with the NS is located
            replica_id: The replica number, in case there are multiple worker in an area.

        Returns:
            The NSD name to be used by upper levels
        """
        logger.info("Creating K8s Network Service Descriptors")
        # The NS id change if controller or worker, on area basis and on the replica number
        ns_id = f'{self.get_id()}_K8S_C' if is_controller else f'{self.get_id()}_K8S_C_A{area.id}_W{replica_id}'
        nsd_type = 'master' if is_controller else 'worker'

        # Building the list of all networks (mgt+data) that is used when building NSD
        net_list = []
        vim_net_mapping_mgt = VimNetMap.build_vnm(
            "mgt",
            "ens3",
            self.k8s_model.config.network_endpoints.mgt,
            True,
            "mgt_net"
        )
        net_list.append(vim_net_mapping_mgt)

        net_n = 4
        # List of data network to be given when building vnfd
        for pool in self.k8s_model.config.network_endpoints.data_nets:
            net_list.append(VimNetMap.build_vnm(
                f"data_{pool.net_name}",
                f"ens{net_n}",
                pool.net_name,
                False
            ))

        data_net_list = list(map(lambda x: x.net_name, self.k8s_model.config.network_endpoints.data_nets))

        # Create the VNFD
        area_type = AreaType.CORE if area.core else AreaType.AREA
        created_vnfd = [self.set_vnfd(is_controller, area_type, area_id=area.id, data_interfaces=data_net_list,
                                      vm_flavor_request=area.worker_flavor_override)]

        nsd_builder = Sol006NSDBuilderBeta(
            created_vnfd,
            self.get_topology().get_vim_name_from_area_id(self.k8s_model.config.core_area.id),
            nsd_id=ns_id,
            nsd_type=nsd_type,
            vl_maps=net_list
        )

        nsd = nsd_builder.get_nsd()

        if not is_controller:
            nsd.area_id = area.id
            nsd.replica_id = replica_id

        # Append to the NSD list the created NSD.
        self.base_model.nsd_.append(nsd)
        self.to_db()  # Save the model

        return ns_id

    def set_vnfd(self, is_controller: bool, area_type: AreaType, area_id: Optional[int] = None,
                 data_interfaces: Optional[list] = None,
                 vm_flavor_request: Optional[VMFlavors] = None, replica: int = 0) -> BlueVNFD:
        """
        Set the Virtual network function descriptor for an area (both core area and normal area).

        Args:
            is_controller: indicates if it is the k8s controller (or master)
            area_type: the area type
            area_id: the optional area id (for not core areas)
            data_interfaces: optional virtual link descriptors for data interfaces
            vm_flavor_request: optional VM flavors to override default ones.
            replica: the replica number of the worker

        Returns:
            the created VNFD
        """
        logger.debug(f"Setting VNFd located in area >{area_id}<")

        # ID format change if area_type == core or area_type == area
        vnfd_id = f'{self.get_id()}_AC' if is_controller else f'{self.get_id()}_A{area_id}_R{replica}'
        vdu_id = 'AC' if is_controller else f"A{area_id}_R{replica}"

        if is_controller:
            created_vdu = VirtualDeploymentUnit.build_vdu(vdu_id, VDU_IMAGE, data_interfaces, CONTROLLER_FLAVOR)
        else:
            created_vdu = VirtualDeploymentUnit.build_vdu(vdu_id, VDU_IMAGE, data_interfaces,
                                                          vm_flavor_request if vm_flavor_request else WORKERS_FLAVOR)

        created_vnfd = VirtualNetworkFunctionDescriptor.build_vnfd(
            vnfd_id,
            DEFAULT_USR,
            DEFAULT_PASSWD,
            True,
            vdu_list=[created_vdu]
        )

        # Build the VNF package and upload the package on OSM
        built_vnfd_package = Sol006VnfdBuilderBeta(created_vnfd, hemlflexcharm=True, cloud_init=True)

        vnfd_summary = built_vnfd_package.get_vnf_blue_descr_only_vdu()

        if area_type == AreaType.CORE:
            self.base_model.vnfd.core.append(vnfd_summary)
        else:
            self.base_model.vnfd.area.append(vnfd_summary)

        self.to_db()

        return vnfd_summary

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
        master_nsd = next(item for item in self.base_model.nsd_ if item.type == 'master')
        # Create a configurator for the k8s controller and dumps the actions to be executed into conf_dump
        conf_dump = ConfiguratorK8sBeta(master_nsd.descr.nsd.nsd[0].id, 1, self.get_id(), self.k8s_model,
                                        role='master', step=1).dump()
        # saving the id of the action because we need to post process its output
        # self.action_to_check.append(conf_[0]['param_value']['action_id'])
        self.base_model.action_to_check.append(conf_dump[0]['primitive_data']['primitive_params']['config-content'])
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
            self.k8s_model.config.master_key_add_worker = parse_ansible_output(action_output, playbook_name,
                                                                               'worker join key', 'msg')
            self.k8s_model.config.master_credentials = parse_ansible_output(action_output, playbook_name,
                                                                            'k8s credentials', 'msg')['stdout']

            # If there is a floating IP, we need to use this one in the k8s config file (instead of the internal one)
            self.k8s_model.config.master_credentials = re.sub("https:\/\/(.*):6443", f"https://{self.k8s_model.config.controller_ip}:6443", self.k8s_model.config.master_credentials)
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
            checked_area = next((item for item in self.k8s_model.areas if item.id == area.id), None)
            if checked_area:
                raise ValueError("Blue {} - area {} already exists!".format(self.get_id(), area.id))
            for index in range(1, area.workers_replica + 1):
                logger.info("Blue {} - adding worker {} on area {}".format(self.get_id(), index, area.id))
                nsd_names.append(self.set_nsd(is_controller=False, area=area, replica_id=index))
            self.k8s_model.areas.append(area)

        for area in msg.modify_areas:
            # check if area is already existing in self.conf, or it is a new area
            checked_area = next((item for item in self.k8s_model.areas if item.id == area.id), None)
            if checked_area:
                # area already existing, checking replicas
                if checked_area.workers_replica < area.workers_replica:
                    for index in range(checked_area.workers_replica + 1, area.workers_replica):
                        logger.info("Blue {} - adding worker {} on area {}".format(self.get_id(), index, area.id))
                        nsd_names.append(self.set_nsd(is_controller=False, area=area, replica_id=index))
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
            areas = self.k8s_model.areas
        elif type(msg) is K8sBlueprintScale:
            # Otherwise, for example in scaling operation, we receive an object of type K8sBlueprintScale
            msg_ojb: K8sBlueprintScale = msg
            areas = msg_ojb.add_areas
        else:
            logger.warning("Message type non recognized {}".format(msg))
            areas = []

        for area in areas:
            for n in self.base_model.nsd_:
                # For each network service descriptor in the area we check that the NS is a 'worker'
                if n.type == 'worker' and n.area_id == area.id:
                    # We build a configurator that will give us back the instructions to be executed via ansible on the
                    # worker
                    res += ConfiguratorK8sBeta(
                        n.descr.nsd.nsd[0].name,
                        1,
                        self.get_id(),
                        self.k8s_model,
                        role='worker',
                        master_key=self.k8s_model.config.master_key_add_worker
                    ).dump()

        logger.debug("K8s worker configuration built")
        self.to_db()
        # The resources to be executed are returned and then executed by the caller on the workers
        return res

    def add_worker_area_label(self, msg):
        """
        Add the labels on k8s worker nodes. The label must be added through the controller since it is a k8s instruction.

        Args:
            msg: if this method is called in the init phase, the message is the creation request, then we retrieve the
            workers to be labeled from the blue config model. If it is called by a scaling operation, we can get the
            workers to be labeled from this argument (K8sBlueprintScale).
        """
        logger.debug("Blue {} - Triggering Day2 Add area label to workers ".format(self.get_id()))
        if type(msg) is dict:
            # If the request is coming from initial config, msg is a dict (depends on NFVCL code).
            # But since the message is the same on witch, the object is build we can use the data in config model that is
            # the same.
            areas = self.k8s_model.areas
        elif type(msg) is K8sBlueprintScale:
            # Otherwise, for example, in scaling operation, we receive an object of type K8sBlueprintScale
            msg_ojb: K8sBlueprintScale = msg
            areas = msg_ojb.add_areas
        else:
            logger.warning("Message type non recognized {}".format(msg))
            areas = []

        areas_to_label = [item.id for item in areas]
        workers_to_label = []
        for area_id in areas_to_label:
            # Looks for the workers to be labeled in the k8s cluster
            conf_area = next((item for item in self.k8s_model.areas if item.id == area_id), None)
            if not conf_area:
                raise ValueError('Blue {} - configuration area {} not found'.format(self.get_id(), area_id))

            # looking for workers' vdu names (they are the names seen by the K8s master)
            vm_names = []
            for n in self.base_model.nsd_:
                if n.type == 'worker' and n.area_id == area_id:
                    vnfi = nbiUtil.get_vnfi_list(n.nsi_id)[0]
                    vm_names.append(vnfi['vdur'][0]['name'])
            workers_to_label.append({'area': area_id, 'vm_names': vm_names})

        configurator = ConfiguratorK8sBeta(
            next(item.descr.nsd.nsd[0].id for item in self.base_model.nsd_ if item.type == 'master'),
            1,
            self.get_id(),
            self.k8s_model,
            role='master',
            step=2
        )
        configurator.add_worker_label(workers_to_label)
        return configurator.dump()

    def add_to_topology(self, callback_msg):
        """
        Once the K8s cluster is ready, it is added to the topology.
        In this way, it is possible to use the cluster to deploy services on top of K8s through the NFVCL.
        """
        for primitive in callback_msg:
            if primitive['result']['charm_status'] != 'completed':
                raise ValueError('in k8s blue -> add_to_topology callback charm_status is not completed')

        vim = self.get_topology().get_vim_from_area_id_model(self.k8s_model.config.core_area.id)
        self.k8s_model.vim_name = vim.name
        self.to_db()  # Saving the vim name
        self.get_topology().add_k8scluster(self.k8s_model.parse_to_k8s_topo_model(vim_name=vim.name))

    def install_plugins(self, msg: dict):
        """
        Day 2 operation. Install k8s plugins after the cluster has been initialized.
        Suppose that there are NO plugin installed.

        Args:
            msg: The received message. IT is not used but necessary otherwise crash.

        Returns:
            Empty primitive list such that caller does not crash.
        """
        client_config = get_k8s_config_from_file_content(self.k8s_model.config.master_credentials)
        # Build plugin list
        plug_list: List[K8sPluginName] = []

        if self.k8s_model.config.cni == 'flannel':
            plug_list.append(K8sPluginName.FLANNEL)
        elif self.k8s_model.config.cni == 'calico':
            plug_list.append(K8sPluginName.CALICO)
        plug_list.append(K8sPluginName.METALLB)
        plug_list.append(K8sPluginName.OPEN_EBS)

        workers_mgt_int = []
        for area in self.k8s_model.areas:
            for worker_interface in area.worker_mgt_int.values():
                workers_mgt_int.append(worker_interface.vld[0].get_ip_str()[0]) # Taking the first ip that should be the floating in case present

        # Get the pool list for metal load balancer
        pool_list = self.k8s_model.config.network_endpoints.data_nets
        # Get the k8s pod network cidr
        pod_network_cidr = get_k8s_cidr_info(client_config)
        # create additional data for plugins (lbpool and cidr)
        add_data = K8sTemplateFillData(pod_network_cidr=pod_network_cidr, lb_ipaddresses=workers_mgt_int,
                                       lb_pools=pool_list)

        install_plugins_to_cluster(kube_client_config=client_config, plugins_to_install=plug_list,
                                   template_fill_data=add_data, cluster_id=self.base_model.id)

        # Returning empty primitive list to avoid error.
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
            checked_area = next((item for item in self.k8s_model.areas if item.id == area.id), None)
            if not checked_area:
                raise ValueError("Blue {} - area {} not found".format(self.get_id(), area.id))

            logger.debug("Blue {} - deleting K8s workers on area {}".format(self.get_id(), area.id))
            # find nsi to be deleted
            for nsd in self.base_model.nsd_:
                if nsd.type == 'worker':
                    if nsd.area_id == area.id:
                        logger.debug("Worker on area {} has nsi_id: {}".format(area.id, nsd.nsi_id))
                        nsi_to_delete.append(nsd.nsi_id)
            # removing items from conf
            # Note: this should be probably done, after deletion confirmation from the nfvo
            self.k8s_model.areas = [item for item in self.k8s_model.areas if item.id != area.id]

        for area in msg.modify_areas:
            # check if area is already existing in self.conf, or it is a new area
            checked_area = next((item for item in self.k8s_model.areas if item.id == area.id), None)
            if checked_area:
                # area already existing, checking replicas
                if checked_area.workers_replica > area.workers_replica:
                    nsi_ids = [item for item in self.base_model.nsd_ if item.area_id == area.id]
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
        val = getattr(self, 'k8s_model', None)
        # If this is the first time the config model will be 'None' and we need to load the data from self.conf (that is
        # coming from the database)

        if val:
            # We update self.conf that is SAVED into the DB, differently from self.config_model.
            # In this way the model will be saved into the DB
            self.base_model.conf = self.k8s_model.model_dump()
        else:
            # If the blueprint instance is loaded for the first time, then the model is empty, and we can parse the
            # dictionary into the model
            self.k8s_model = K8sBlueprintModel.model_validate(self.base_model.conf)
        # To save the data (in particular the self.conf variable) we call the super method
        super(K8sBlue, self).to_db()

    def _destroy(self):
        """
        Called when the blueprint is destroyed.
        """
        logger.info("Destroying")

        # Removing monitoring by prometheus
        self.disable_scraping()

        # K8s cluster is removed from the topology and from OSM if present
        topo: Topology = self.get_topology()
        try:
            topo.get_k8s_cluster(self.get_id())
            topo.del_k8scluster(self.get_id())
        except ValueError as e:
            logger.warning(e)
            logger.warning("The Cluster was not present in the topology, it will not be removed from it.")

        # Release the reserved IP addresses for the Load Balancer (see
        self.get_topology().release_ranges(self.get_id())

    def get_ip(self) -> None:
        """
        Retrieve information about VM instances IPs.

        VMs are spawned by OSM and OpenStack; we do not decide IPs to be assigned to VMs.
        For this reason, it is necessary to obtain this data after they have been created.
        """
        logger.debug('getting IP addresses from vnf instances')

        for nsd in self.base_model.nsd_:
            if nsd.type == 'master':
                # Retrieve the complete virtual link descriptors for the only interface of the k8s controller!
                vlds = get_ns_vld_model(nsd.nsi_id, ["mgt"])
                ip_mgt_list = vlds["mgt"][0].get_ip_str()

                self.k8s_model.config.controller_ip = ip_mgt_list[0] # Taking the first ip that should be the floating in case present
                # If we have a floating IP, we assign the internal IP. Otherwise the same IP is internal/external
                self.k8s_model.config.controller_internal_ip = ip_mgt_list[0] if len(ip_mgt_list)<=1 else ip_mgt_list[1]
            if nsd.type == 'worker':
                # Looking for the area corresponding to the actual NSD
                target_area = next(area for area in self.k8s_model.areas if area.id == nsd.area_id)
                if not target_area.worker_data_int:
                    target_area.worker_data_int = {}
                # links
                vld_names = ["mgt"]
                for pool in self.k8s_model.config.network_endpoints.data_nets:
                    # If the net is not the management one
                    if pool.net_name != self.k8s_model.config.network_endpoints.mgt:
                        # Then append the net to virtual link descriptors
                        vld_names.append('data_{}'.format(pool.net_name))

                # Retrieve the complete virtual link descriptors for every link of the network service (k8s WORKER)!
                vlds: dict[str, List[VirtLinkDescr]] = get_ns_vld_model(nsd.nsi_id, vld_names)

                # Need to add interfaces names such that we can assign the correct ip later on!
                target_area.worker_mgt_int[str(nsd.replica_id)] = K8sNsdInterfaceDesc(
                    nsd_id=nsd.nsi_id,
                    nsd_name=nsd.descr.nsd.nsd[0].name,
                    vld=[VirtLinkDescr.model_validate(vlds["mgt"][0])])

                nsd_data_int_key = next(item for item in vlds if item != 'mgt')
                target_area.worker_data_int[nsd.replica_id] = K8sNsdInterfaceDesc(
                    nsd_id=nsd.nsi_id,
                    nsd_name=nsd.descr.nsd.nsd[0].name,
                    vld=vlds[nsd_data_int_key])
            self.to_db()

    def get_data(self, get_request: BlueGetDataModel) -> dict:

        client_config = get_k8s_config_from_file_content(self.k8s_model.config.master_credentials)
        info = get_k8s_cidr_info(client_config)

        # TODO IMPLEMENT IF NECESSARY
        logger.info(get_request.model_dump_json())

        return {}


    def prom_pre_checks(self, prom_info: BluePrometheus):
        """
        Checks that the specified prometheus server exists in the topology
        Args:
            prom_info: The message coming from the request

        Returns:
            An empty list of day2 primitives, checks do not need something to be executed
        """
        topology = build_topology()
        # Raise Error if the prometheus server is not present
        prom_server = topology.get_prometheus_server(prom_info.prom_server_id)

        return [] # Return an empty list of day 2 primitives


    # Do not remove unused parameter, otherwise it crashes for unexpected parameter when called!!!
    def enable_node_exporter(self, prom_info: BluePrometheus):
        """
        Install in every area and every NSD the prometheus-node-exporter.
        - For each nsd it creates a configurator and dumps the configuration to be executed.
        - Every configuration is executed, and node-exporter is installed on every K8s worker and the controller.
        - Save the list of node exporters in the base_model that will be used in the parent class to set up the
          prometheus job.

        Returns:
            configuration dumps to be executed on the target nodes.
        """
        res = []
        prom_target_list = []  # List to store all node exporters for server configuration

        # For each area we install, through APT install, the package node prometheus-node-exporter on every NSD
        for nsd in self.base_model.nsd_:
            nsd_item = nsd.descr.nsd.nsd[0]
            configurator = ConfiguratorK8sBeta(
                nsd_item.id,
                1,
                self.get_id(),
                self.k8s_model,
                role='worker',
                master_key=self.k8s_model.config.master_key_add_worker
            )
            configurator.resetPlaybook()

            # We need to set mgt IP to add prometheus node exporter, of each NSD, as prometheus target on the server.
            # If it is master
            if nsd.type == 'master':
                configurator.set_mng_ip(self.k8s_model.config.controller_ip)
                prom_target = PrometheusTargetModel()
                prom_target.targets.append(self.k8s_model.config.controller_ip + ":9100")
                prom_target.labels = {"type": "controller", "blue_id": self.get_id()}
                prom_target_list.append(prom_target)  # Adding to the node list
            else:
                # In case of worker we need to identify witch is the correct mgt IP of this worker
                # We select the correct area (corresponding to the actual NSD)
                area = next((area for area in self.k8s_model.areas if area.id == nsd.area_id), None)
                if area is not None:
                    # In the area we get the router that has the same nsd_name
                    target_router_nsd_int = next((router_nsd_int for router_nsd_int in area.worker_mgt_int.values()
                                                  if router_nsd_int.nsd_name == nsd_item.name), None)
                    if target_router_nsd_int is not None:  # If found
                        # Add the FIRST management IP as management IP
                        configurator.set_mng_ip(target_router_nsd_int.vld[0].ip)
                        prom_target = PrometheusTargetModel()
                        prom_target.targets.append(target_router_nsd_int.vld[0].ip + ":9100")
                        prom_target.labels = {"type": "node", "blue_id": self.get_id()}
                        prom_target_list.append(prom_target)  # Adding to the node list
                else:
                    logger.warning("Area not found when trying to enable prometheus")
                    continue  # Skip the current iteration

            # We dump the content to be executed on the node for each node
            res += configurator.enable_prometheus()

        # Saving the node exporter list to be permanent (and used by enable_scraping function)
        self.base_model.node_exporters = prom_target_list
        # Setting the prometheus server as scraper for this blueprint
        self.base_model.prometheus_scraper_id = prom_info.prom_server_id
        self.to_db()
        return res

    def enable_scraping(self, prom_info: BluePrometheus):
        """
        Set a scraping job on the requested prometheus server instance. See setup_prom_scraping method for further info.
        Args:
            prom_info: The info on the prometheus server instance, coming from the request.

        """
        self.setup_prom_scraping(prom_info=prom_info)
        return []  # Return empty since VNFM does not have to execute tasks.

    def disable_scraping(self, prom_info: BluePrometheus = None):
        """
        Disable and remove all scraping jobs by the prometheus server on this blueprint. It does not remove node exporters from each k8s node.
        """
        self.disable_prom_scraping()

        return []
