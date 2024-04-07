from ipaddress import IPv4Address
from typing import Optional, List
import re

from netaddr.ip import IPNetwork
from blueprints_ng.lcm.blueprint_route_manager import add_route
from blueprints_ng.modules.k8s.config.k8s_day2_configurator import VmK8sDay2Configurator
from blueprints_ng.modules.k8s.config.k8s_dayN_configurator import VmK8sDayNConfigurator
from models.http_models import HttpRequestType
from models.k8s.common_k8s_model import Cni, LBPool
from models.k8s.plugin_k8s_model import K8sPluginName, K8sTemplateFillData
from utils.k8s import get_k8s_config_from_file_content, install_plugins_to_cluster, get_k8s_cidr_info
from models.k8s.topology_k8s_model import K8sModel, K8sVersion
from starlette.requests import Request
from topology.topology import Topology, build_topology
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.modules.k8s.config.k8s_day0_configurator import VmK8sDay0Configurator
from models.blueprint_ng.k8s.k8s_rest_models import K8sCreateModel, K8sAreaDeployment, K8sAddNodeModel, KarmadaInstallModel, K8sDelNodeModel, CreateVxLanModel
from blueprints_ng.resources import VmResource, VmResourceImage, VmResourceFlavor
from pydantic import Field
from blueprints_ng.blueprint_ng import BlueprintNGState, BlueprintNG

K8S_BLUE_TYPE = "k8s"
BASE_IMAGE_MASTER = "k8s-base"
BASE_IMAGE_URL = "http://images.tnt-lab.unige.it/k8s/k8s-v0.0.1.qcow2"
BASE_IMAGE_WORKER = "k8s-base"
DUMMY_NET_INT_NAME = "eth99"
POD_NET_CIDR = "10.254.0.0/16"
POD_SERVICE_CIDR = "10.200.0.0/16"
K8S_DEFAULT_PASSWORD = "ubuntu"
DUMMY_NET_CIDR= "10.252.252.0/24"
DUMMY_NET_POOL_START_IP = str((IPNetwork(DUMMY_NET_CIDR))[20])
DUMMY_NET_VM_START_IP = str((IPNetwork(DUMMY_NET_CIDR))[1])

class K8sBlueprintNGState(BlueprintNGState):
    """

    """
    version: K8sVersion = Field(default=K8sVersion.V1_29) # CRASH
    cni: Cni = Field(default=Cni.flannel)

    pod_network_cidr: str = Field(default=POD_NET_CIDR)
    pod_service_cidr: str = Field(default=POD_SERVICE_CIDR)
    reserved_pools: List[LBPool] = Field(default=[], description="The IP pools dedicated for service exposure")


    worker_numbers: List[int] = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0] # We can have at maximum 18 workers. This is used to reserve the number of workers.
    master_area: Optional[K8sAreaDeployment] = Field(default=None)
    password: str = Field(default=K8S_DEFAULT_PASSWORD)
    topology_onboarded: bool = Field(default=False)
    area_list: List[K8sAreaDeployment] = []
    attached_networks: List[str] = []

    vm_master: Optional[VmResource] = Field(default=None)
    vm_master_configurator: Optional[VmK8sDay0Configurator] = Field(default=None)

    vm_workers: List[VmResource] = []

    day_0_master_configurator: Optional[VmK8sDay0Configurator] = Field(default=None)
    day_0_workers_configurators: List[VmK8sDay0Configurator] = []
    day_0_workers_configurators_tobe_exec: List[VmK8sDay0Configurator] = []

    day_2_master_configurator: Optional[VmK8sDay2Configurator] = Field(default=None)

    master_key_add_worker: str = Field(default="", description="The master key to be used by a worker to join the k8s cluster")
    master_credentials: str = Field(default="", description="The certificate of the admin, to allow k8s administration")

    def remove_worker(self, worker_to_be_rem: VmResource):
        """
        Removes a worker and its configurators from the state.
        Args:
            worker_to_be_rem: The worker name to be removed
        """
        # Destroying configurator and releasing the worker number, Remove worker resources from the state
        self.vm_workers = [worker for worker in self.vm_workers if worker.name != worker_to_be_rem.name]
        # TODO check working
        for configurator in self.day_0_workers_configurators:
            if configurator.vm_resource.name == worker_to_be_rem.name:
                self.release_worker_number(configurator.vm_number)
                self.day_0_workers_configurators.remove(configurator)
        #self.day_0_workers_configurators = [configur for configur in self.day_0_workers_configurators if configur.vm_resource.name != worker_to_be_rem.name]
        self.day_0_workers_configurators_tobe_exec = [configur for configur in self.day_0_workers_configurators_tobe_exec if configur.vm_resource.name != worker_to_be_rem.name]

    def get_reserved_ip_list(self) -> List[str]:
        """
        Return a list of IPs reserved for k8s services, from all the pools.
        """
        ip_list = []
        for pool in self.reserved_pools:
            ip_list.extend(pool.get_ip_address_list())
        return ip_list

    def reserve_worker_number(self):
        position = 0
        for val in self.worker_numbers:
            if val == 0:
                self.worker_numbers[position] = 1
                return position
            position += 1
        raise ValueError("Cannot assign number to a worker, all numbers has been reserved.")

    def release_worker_number(self, number: int) -> None:
        if self.worker_numbers[number] == 1:
            self.worker_numbers[number] = 0
        else:
            raise ValueError("The worker number was not reserved")


@declare_blue_type(K8S_BLUE_TYPE)
class K8sBlueprint(BlueprintNG[K8sBlueprintNGState, K8sCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = K8sBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: K8sCreateModel):
        """
        Creates the master node in the master area.
        Creates the desired number of worker nodes in the desired areas
        Starts the DAY-0 configuration of master and worker nodes.
        Installs default plugins to the cluster (if required, by default yes)
        """
        super().create(create_model)
        self.logger.info(f"Starting creation of K8s blueprint")
        self.state.pod_network_cidr = create_model.pod_network_cidr
        self.state.pod_service_cidr = create_model.service_cidr
        self.state.cni = create_model.cni
        self.state.password = create_model.password

        area: K8sAreaDeployment
        for area in create_model.areas:     # In each area we deploy workers and in the core area also the master (there is always a core area containing the master)
            if area.is_master_area:
                self.state.master_area = area
                self.deploy_master_node(area, create_model.master_flavors)

            self.deploy_area(area)

        self.setup_networks()
        self.day0conf(create_model.topology_onboard, configure_master=True)
        # Install K8s Plugins if required (default=yes)
        if create_model.install_plugins:
            self.install_default_plugins()

    def deploy_master_node(self, area: K8sAreaDeployment, master_flavors: VmResourceFlavor):
        # Defining Master node. Should be executed only once
        self.state.vm_master = VmResource(
            area=area.area_id,
            name=f"{self.id}_VM_K8S_C",
            image=VmResourceImage(name=BASE_IMAGE_MASTER, url=BASE_IMAGE_URL),
            flavor=master_flavors,
            username="ubuntu",
            password=self.state.password,
            management_network=area.mgmt_net,
            additional_networks=[area.service_net] if area.service_net else []
        )
        # Registering master node
        self.register_resource(self.state.vm_master)
        # Creating the VM
        self.provider.create_vm(self.state.vm_master)
        # Creating the configurator for the master
        self.state.day_0_master_configurator = VmK8sDay0Configurator(vm_resource=self.state.vm_master, vm_number=0)
        self.state.day_2_master_configurator = VmK8sDay2Configurator(vm_resource=self.state.vm_master)
        self.register_resource(self.state.day_0_master_configurator)
        self.register_resource(self.state.day_2_master_configurator)

    def deploy_area(self, area: K8sAreaDeployment):
        for worker_replica_num in range(0, area.worker_replicas):
            # Workers of area X
            worker_number = self.state.reserve_worker_number()
            vm = VmResource(
                area=area.area_id,
                name=f"{self.id}_VM_W_{worker_number}",
                image=VmResourceImage(name=BASE_IMAGE_WORKER, url=BASE_IMAGE_URL),
                flavor=area.worker_flavors,
                username="ubuntu",
                password=self.state.password,
                management_network=area.mgmt_net,
                additional_networks=[area.service_net] if area.service_net else []
            )
            self.state.vm_workers.append(vm)
            # Registering master node
            self.register_resource(vm)
            # Creating the VM
            self.provider.create_vm(vm)

            configurator = VmK8sDay0Configurator(vm_resource=vm, vm_number=worker_number)
            self.state.day_0_workers_configurators.append(configurator)
            self.state.day_0_workers_configurators_tobe_exec.append(configurator)
            self.register_resource(configurator)

        if area.mgmt_net not in self.state.attached_networks:
            self.state.attached_networks.append(area.mgmt_net)
        if area.service_net and area.service_net not in self.state.attached_networks:
            self.state.attached_networks.append(area.service_net)
        if area not in self.state.area_list:
            self.state.area_list.append(area)

    def setup_networks(self):
        # Reserve a range of IP in the service net
        reserved_pools = []
        if self.state.master_area.service_net:
            # In this case, the NET exists on OPENSTACK, and we should work with the topology
            pool = LBPool(net_name=self.state.master_area.service_net, range_length=self.state.master_area.service_net_required_ip_number)
            res_range = build_topology().reserve_range_lb_pool(pool, self.id)  # TODO IP should be reserved in VIM
            # Building IPv4Addresses to validate. Then saving string because obj cannot be serialized.
            pool.ip_start = res_range.start.exploded
            pool.ip_end = res_range.end.exploded
            reserved_pools.append(pool)
        else:
            # In this case, the net is a dummy net (present on all machines), created on day0 by the configurator, so we can do what we want
            pool = LBPool(net_name=DUMMY_NET_INT_NAME, range_length=self.state.master_area.service_net_required_ip_number)
            ip_start_tmp = IPv4Address(DUMMY_NET_POOL_START_IP)
            pool.ip_start = ip_start_tmp.exploded
            pool.ip_end = (ip_start_tmp+pool.range_length).exploded
            reserved_pools.append(pool)

        self.state.reserved_pools = reserved_pools

    @classmethod
    def rest_create(cls, msg: K8sCreateModel, request: Request):
        """
        Creates a K8S cluster using the NFVCL blueprint
        """
        return cls.api_day0_function(msg, request)

    def day0conf(self, topology_onboard: bool, configure_master: bool = False):
        if configure_master:
            # Configuring the master node
            master_conf = self.state.day_0_master_configurator
            if not self.state.master_area.service_net:
                # The master has the first IP (+0) == DUMMY_NET_VM_START_IP
                master_conf.configure_master(self.state.vm_master.get_management_interface().fixed.ip, self.state.vm_master.access_ip, self.state.pod_network_cidr, self.state.pod_service_cidr, self.state.get_reserved_ip_list(), DUMMY_NET_VM_START_IP)
            else:
                master_conf.configure_master(self.state.vm_master.get_management_interface().fixed.ip, self.state.vm_master.access_ip, self.state.pod_network_cidr, self.state.pod_service_cidr, [], DUMMY_NET_VM_START_IP)
            master_result = self.provider.configure_vm(master_conf)

            # REGISTERING GENERATED VALUES FROM MASTER CONFIGURATION
            self.state.master_key_add_worker = re.sub("[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:6443", f"{self.state.vm_master.access_ip}:6443", master_result['kubernetes_join_command']['stdout']) #
            # If there is a floating IP, we need to use this one in the k8s config file (instead of the internal one)
            self.state.master_credentials = re.sub("https:\/\/(.*):6443", f"https://{self.state.vm_master.access_ip}:6443", master_result['credentials_file']['stdout'])

        # Configuring ONLY worker nodes that have not yet been configured and then removing from the list
        for configurator in self.state.day_0_workers_configurators_tobe_exec:
            configurator.configure_worker(self.state.master_key_add_worker, self.state.master_credentials, DUMMY_NET_VM_START_IP)
            worker_result = self.provider.configure_vm(configurator)
            self.state.day_0_workers_configurators_tobe_exec.remove(configurator)

        # If required, onboarding the cluster in the topology
        if topology_onboard:
            topo: Topology = build_topology()
            area_list = [item.area_id for item in self.state.area_list]

            k8s_cluster = K8sModel(name=self.id, provided_by="NFVCL", blueprint_ref=self.id, credentials=self.state.master_credentials, vim_name=topo.get_vim_name_from_area_id(self.state.master_area.area_id), # For the constraint on the model, there is always a master area.
                      k8s_version=K8sVersion.V1_29, networks=self.state.attached_networks, areas=area_list, cni="", nfvo_onboard=False)
            topo.add_k8scluster(k8s_cluster)
            self.state.topology_onboarded = topology_onboard

    def install_default_plugins(self):
        """
        Day 2 operation. Install k8s default plugins after the cluster has been initialized.
        Suppose that there is NO plugin installed.
        """
        client_config = get_k8s_config_from_file_content(self.state.master_credentials)
        # It builds plugin list
        plug_list: List[K8sPluginName] = []

        if self.state.cni == Cni.flannel.value:
            plug_list.append(K8sPluginName.FLANNEL)
        elif self.state.cni == Cni.calico.value:
            plug_list.append(K8sPluginName.CALICO)
        plug_list.append(K8sPluginName.METALLB)
        plug_list.append(K8sPluginName.OPEN_EBS)

        # IP on the management inteface for the workers, the ones mapped with the floating IP if present
        workers_mgt_int = [item.get_management_interface().fixed.ip for item in self.state.vm_workers]

        # Get the k8s pod network cidr
        pod_network_cidr = get_k8s_cidr_info(client_config) # TODO TIMEOUT
        # Create additional data for plugins (lbpool and cidr)
        add_data = K8sTemplateFillData(pod_network_cidr=pod_network_cidr, lb_ipaddresses=workers_mgt_int,
                                       lb_pools=self.state.reserved_pools)

        install_plugins_to_cluster(kube_client_config=client_config, plugins_to_install=plug_list,
                                   template_fill_data=add_data, cluster_id=self.base_model.id)

    @classmethod
    def add_k8s_worker(cls, msg: K8sAddNodeModel, blue_id: str, request: Request):
        """
        Adds a kubernetes node to a blueprint generated K8S cluster.
        """
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(K8S_BLUE_TYPE, "/add_node", [HttpRequestType.POST], add_k8s_worker)
    def add_worker(self, model: K8sAddNodeModel):
        """
        Elaborates the request to add WORKER nodes to (multiple) area(s).
        First it deploys the workers, then it configures them.
        Args:
            model: The request containing information about workers to be added and in witch area
        """
        area: K8sAreaDeployment
        for area in model.areas:
            # THERE ARE NO MASTER AREAS in the request -> THERE IS A CONSTRAINT IN THE REQUEST MODEL
            self.deploy_area(area)

        self.day0conf(topology_onboard=False, configure_master=False)

    @classmethod
    def del_k8s_workers(cls, msg: K8sDelNodeModel, blue_id: str, request: Request):
        """
        Destroy a worker from a blueprint generated K8S cluster. The number of nodes (controller/master + workers) cannot be lower than 2.

        Args:

            msg: The list of VM names to be deleted from the K8S cluster
            blue_id: The blueprint from witch the node is removed
            request: The request details
        """
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(K8S_BLUE_TYPE, "/del_workers", [HttpRequestType.DELETE], del_k8s_workers)
    def del_workers(self, model: K8sDelNodeModel):
        """
        Delete (multiple) workers from this blueprint generated K8S cluster
        Args:
            model: The list of VM names to be deleted from the K8S cluster

        """
        vm_to_be_destroyed = [] # The list of VM to be destroyed (After the check that exist)
        # If one of the nodes to be removed is the MASTER, let's remove it
        if self.state.vm_master.name in model.node_names:
            # Removing the master node from the list and logging error
            model.node_names.pop(model.node_names.index(self.state.vm_master.name))
            self.logger.error(f"Master node {self.state.vm_master.id} cannot be deleted from cluster {self.id}. Moving to next nodes to be deleted")
        # If the number of workers will be zero. STOP
        if len(self.state.vm_workers) <= 1:
            self.logger.error(f"The number of workers cannot be lower than 1. Pods are scheduled only on workers node, there will be no schedule.")
            return

        dayNconf = VmK8sDayNConfigurator(vm_resource=self.state.vm_master)  # Removing the nodes on a cluster requires actions performed on the master node.
        for node in model.node_names:
            target_vm = [vm for vm in self.state.vm_workers if vm.name == node] # Checking that the node to be removed EXISTS
            if len(target_vm) >= 1:
                dayNconf.delete_node(target_vm[0].get_name_k8s_format()) # Adding the action to remove it from the cmaster/controller.
                vm_to_be_destroyed.append(target_vm[0]) # Appending the VM to be deleted.
            else:
                self.logger.error(f"Node >{node}< has not been found, cannot be deleted from cluster {self.id}. Moving to next nodes to be deleted")
        # Removing from the cluster every VM to be deleted before it will be destroyed (Nodes is removed from k8s cluster by master configurator)
        self.provider.configure_vm(dayNconf)
        # Destroying every VM to be removed from the cluster
        for vm in vm_to_be_destroyed:
            # Delete the VM from the provider
            self.provider.destroy_vm(vm)
            # Delete from registered resources
            self.deregister_resource(vm)
            # Destroying configurator and releasing the worker number, Remove worker resources from the state
            self.state.remove_worker(vm)

    @classmethod
    def configure_k8s_karmada(cls, msg: KarmadaInstallModel, blue_id: str, request: Request):
        """
        Install and configure submariner and Karmada on an existing blueprint generated K8S cluster.
        """
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(K8S_BLUE_TYPE, "/install_karmada", [HttpRequestType.POST], configure_k8s_karmada)
    def configure_karmada(self, model: KarmadaInstallModel):
        """
        Creates a configurator that installs and configures submarine and karmada.
        """
        master_conf = self.state.day_0_master_configurator
        master_conf.install_karmada(model)
        master_result = self.provider.configure_vm(master_conf)

    @classmethod
    def configure_vxlan(cls, msg: CreateVxLanModel, blue_id: str, request: Request):
        """
        Install and configure submariner and Karmada on an existing blueprint generated K8S cluster.
        """
        return cls.api_day2_function(msg, blue_id, request)

    @add_route(K8S_BLUE_TYPE, "/create_vx_lan", [HttpRequestType.POST], configure_vxlan)
    def setup_vxlan(self, model: CreateVxLanModel):
        """
        Creates a vxlan interface on the k8s master node and configure it to be accessible from the given client IP in the request.
        """
        # If the server IP is not specified in the request, it binds the vxlan on the management interface
        if not model.vx_server_ip:
            model.vx_server_ip = self.state.vm_master.get_management_interface().fixed.ip
            model.vx_server_ext_device = self.state.vm_master.get_management_interface().fixed.interface_name

        master_day2_conf = self.state.day_2_master_configurator

        # If the controller has a floating IP, the client config is built on that IP (the one seen by the client)
        if self.state.vm_master.get_management_interface().floating:
            client_commands: str = master_day2_conf.configure_vxlan(model, self.state.vm_master.get_management_interface().floating.ip)
        else:
            client_commands: str = master_day2_conf.configure_vxlan(model)

        # Prints the list of command to be executed on the vxlan client to connect at the master node
        self.logger.info(f"Client configuration: \n{client_commands}")
        master_result = self.provider.configure_vm(master_day2_conf)

    def destroy(self):
        """
        Destroy the blueprints. Calls super destroy that destroy VMs and configurators.
        Then release all the reserved resources in the topology.
        """
        # TODO check if there is something deployed on the cluster -> MAKE IMPOSSIBLE TO REMOVE IT OR REQUIRE OVERRIDE.
        super().destroy()
        # Remove reserved IP range
        build_topology().release_ranges(self.id) # Remove all reserved ranges in the networks
        # If it was onboarded on the topology (as a usable k8s cluster), remove it.
        if self.state.topology_onboarded:
            try:
                build_topology().del_k8scluster(self.id)
            except ValueError:
                self.logger.error(f"Could not delete K8S cluster {self.id} from topology: NOT FOUND")
