import re
from typing import Optional, List

from netaddr.ip import IPNetwork
from pydantic import Field

from nfvcl.blueprints_ng.blueprint_ng import BlueprintNGState, BlueprintNG
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type, day2_function
from nfvcl.blueprints_ng.modules.k8s.config.k8s_day0_configurator import VmK8sDay0Configurator
from nfvcl.blueprints_ng.modules.k8s.config.k8s_day2_configurator import VmK8sDay2Configurator
from nfvcl.blueprints_ng.modules.k8s.config.k8s_dayN_configurator import VmK8sDayNConfigurator
from nfvcl.blueprints_ng.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration
from nfvcl.models.blueprint_ng.k8s.k8s_rest_models import K8sCreateModel, K8sAreaDeployment, K8sAddNodeModel, \
    KarmadaInstallModel, K8sDelNodeModel
from nfvcl.models.http_models import HttpRequestType
from nfvcl.models.k8s.common_k8s_model import Cni
from nfvcl.models.k8s.plugin_k8s_model import K8sPluginName, K8sPluginAdditionalData, K8sLoadBalancerPoolArea
from nfvcl.models.k8s.topology_k8s_model import TopologyK8sModel, K8sVersion
from nfvcl.models.network.ipam_models import SerializableIPv4Address, SerializableIPv4Network
from nfvcl.models.topology.topology_models import TopoK8SHasBlueprintException
from nfvcl.topology.topology import Topology, build_topology
from nfvcl.utils.k8s import get_k8s_config_from_file_content, install_plugins_to_cluster, get_k8s_cidr_info, \
    get_config_map, patch_config_map

K8S_BLUE_TYPE = "k8s"
K8S_VERSION = K8sVersion.V1_30
BASE_IMAGE_MASTER = "u24-k8s-base-v0.0.4-rev"
BASE_IMAGE_WORKER = "u24-k8s-base-v0.0.4-rev"
BASE_IMAGE_URL = "https://images.tnt-lab.unige.it/k8s/k8s-v0.0.4-ubuntu2404.qcow2"
DUMMY_NET_INT_NAME = "eth99"
POD_NET_CIDR = SerializableIPv4Network("10.254.0.0/16")
POD_SERVICE_CIDR = SerializableIPv4Network("10.200.0.0/16")
K8S_DEFAULT_PASSWORD = "ubuntu"
DUMMY_NET_CIDR = "10.252.252.0/24"
DUMMY_NET_POOL_START_IP = str((IPNetwork(DUMMY_NET_CIDR))[20])
DUMMY_NET_VM_START_IP = str((IPNetwork(DUMMY_NET_CIDR))[1])


class K8sBlueprintNGState(BlueprintNGState):
    """
    State of K8S blueprint
    """
    # Values coming from the request
    version: K8sVersion = Field(default=K8S_VERSION, description="Indicates the K8S version")

    cni: Cni = Field(default=Cni.flannel, description="The network plugin used by the cluster")
    pod_network_cidr: SerializableIPv4Network = Field(default=POD_NET_CIDR, description="The internal network used for PODs by the cluster")
    pod_service_cidr: SerializableIPv4Network = Field(default=POD_SERVICE_CIDR, description="The internal network used for Services by the cluster")
    cadvisor_node_port: int = Field(default=30080, description="The node port on which the cadvisor service is exposed")

    password: str = Field(default=K8S_DEFAULT_PASSWORD, description="The password set in master and workers node")
    require_port_security_disabled: Optional[bool] = Field(default=True, description="Indicates if the blueprint will require port security disabled (on openstack)")
    topology_onboarded: bool = Field(default=False, description="If the blueprint cluster has to be added to the topology")

    master_area: Optional[K8sAreaDeployment] = Field(default=None, description="A copy of the master area")
    area_list: List[K8sAreaDeployment] = Field(default=[], description="The list of deployed areas")
    # ----------------------------------- Values generated by the Blueprint -----------------------------------------------------------
    load_balancer_ips_area: dict[str, List[SerializableIPv4Address]] = Field(default={}, description="The IPs used by the load balancer indexed by the area")
    load_balancer_pools: List[K8sLoadBalancerPoolArea] = Field(default=[], description="The K8sTemplateArea filled when calculating the load balancer pools")

    worker_numbers: List[int] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # We can have at maximum 18 workers. This is used to reserve the number of workers.
    attached_networks: List[str] = Field(default=[], description="A list of networks attached to all the nodes from every area. Every are can have different networks")
    # VM Master/Controller
    vm_master: Optional[VmResource] = Field(default=None, description="The virtual machine describing the master of the cluster")
    day_0_master_configurator: Optional[VmK8sDay0Configurator] = Field(default=None, description="The DAY0 configurator of the master")
    day_2_master_configurator: Optional[VmK8sDay2Configurator] = Field(default=None, description="The DAY2 configurator of the master")
    # VMs Worker
    vm_workers: List[VmResource] = []
    day_0_workers_configurators: List[VmK8sDay0Configurator] = Field(default=[], description="The DAY0 configurators of the workers")
    day_0_workers_configurators_tobe_exec: List[VmK8sDay0Configurator] = Field(default=[], description="The DAY0 configurators of the workers that have ansible tasks to be executed")
    # Data retrieved and saved from cluster creation
    master_key_add_worker: str = Field(default="", description="The master key to be used by a worker to join the k8s cluster")
    master_credentials: str = Field(default="", description="The certificate of the admin, to allow k8s administration")

    def remove_worker(self, worker_to_be_rem: VmResource) -> List[VmResourceAnsibleConfiguration]:
        """
        Removes a worker and its configurators from the state.
        Args:
            worker_to_be_rem: The worker name to be removed

        Returns the configurator list to be deregistered
        """
        configurators_list: List[VmResourceAnsibleConfiguration] = []
        # Destroying configurator and releasing the worker number, Remove worker resources from the state
        self.vm_workers = [worker for worker in self.vm_workers if worker.name != worker_to_be_rem.name]
        # Looking for configurators of the worker to be removed
        for configurator in self.day_0_workers_configurators:
            if configurator.vm_resource.name == worker_to_be_rem.name:
                self._release_worker_number(configurator.vm_number)
                self.day_0_workers_configurators.remove(configurator)
                configurators_list.append(configurator)
        # Removing configurators to be run from the list, if present
        self.day_0_workers_configurators_tobe_exec = [configur for configur in
                                                      self.day_0_workers_configurators_tobe_exec if
                                                      configur.vm_resource.name != worker_to_be_rem.name]

        return configurators_list

    def get_reserved_ip_list(self) -> List[str]:
        """
        Return a list of IPs reserved for k8s services, from all the pools.
        """
        ip_list = []
        for pool in self.reserved_pools:
            ip_list.extend(pool.get_ip_address_list())
        return ip_list

    def reserve_worker_number(self):
        """
        Reserve worker number in the state, the first free.
        """
        position = 0
        for val in self.worker_numbers:
            if val == 0:
                self.worker_numbers[position] = 1
                return position
            position += 1
        raise ValueError("Cannot assign number to a worker, all numbers has been reserved.")

    def _release_worker_number(self, number: int) -> None:
        """
        Release a worker number from the state
        Args:
            number: The number to be released
        """
        if self.worker_numbers[number] == 1:
            self.worker_numbers[number] = 0
        else:
            raise ValueError("The worker number was not reserved")


@blueprint_type(K8S_BLUE_TYPE)
class K8sBlueprint(BlueprintNG[K8sBlueprintNGState, K8sCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = K8sBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: K8sCreateModel):
        """
        Creates a K8S cluster using the NFVCL blueprint

        Initialize a K8S blueprint.
        1 - Creates the master node in the master area.
        2 - Creates the desired number of worker nodes in the desired areas
        3 - Starts the DAY-0 configuration of master and worker nodes.
        4 - Installs default plugins to the cluster (if required, by default yes)
        """
        super().create(create_model)
        self.logger.info(f"Starting creation of K8s blueprint")
        self.state.pod_network_cidr = create_model.pod_network_cidr
        self.state.pod_service_cidr = create_model.service_cidr
        self.state.cni = create_model.cni
        self.state.password = create_model.password
        self.state.cadvisor_node_port = create_model.cadvisor_node_port

        area: K8sAreaDeployment
        for area in create_model.areas:  # In each area we deploy workers and in the core area also the master (there is always a core area containing the master)
            if area.is_master_area:
                self.state.master_area = area
                self.state.require_port_security_disabled = create_model.require_port_security_disabled
                self.deploy_master_node(area, create_model.master_flavors)
            if len(area.load_balancer_pools_ips) > 0:
                self.state.load_balancer_ips_area[str(area.area_id)] = area.load_balancer_pools_ips
            self.deploy_area(area)

        # Start initial configuration, first it get network list ready. Set self.state.reserved_pools
        self.setup_load_balancer_pool()
        self.day0conf(configure_master=True)
        # Fix DNS Problem
        self.fix_dns_problem()
        # Install K8s Plugins if required (default=yes)
        if create_model.install_plugins:
            self.install_default_plugins()

        # If required, onboarding the cluster in the topology
        if create_model.topology_onboard:
            topo: Topology = build_topology()
            area_list = [item.area_id for item in self.state.area_list]

            k8s_cluster = TopologyK8sModel(name=self.id, provided_by="NFVCL", blueprint_ref=self.id,
                                           credentials=self.state.master_credentials,
                                           vim_name=topo.get_vim_name_from_area_id(self.state.master_area.area_id),
                                           # For the constraint on the model, there is always a master area.
                                           k8s_version=K8sVersion.V1_29, networks=self.state.attached_networks, areas=area_list,
                                           cni="", nfvo_onboard=False, cadvisor_node_port=self.state.cadvisor_node_port,
                                           anti_spoofing_enabled=not self.state.require_port_security_disabled)
            topo.add_k8scluster(k8s_cluster)
            self.state.topology_onboarded = create_model.topology_onboard

    def deploy_master_node(self, area: K8sAreaDeployment, master_flavors: VmResourceFlavor):
        # Defining Master node. Should be executed only once.
        self.state.vm_master = VmResource(
            area=area.area_id,
            name=f"{self.id.lower()}-vm-k8s-c",
            image=VmResourceImage(name=BASE_IMAGE_MASTER, url=BASE_IMAGE_URL),
            flavor=master_flavors,
            username="ubuntu",
            password=self.state.password,
            management_network=area.mgmt_net,
            additional_networks=area.additional_networks,
            require_port_security_disabled=self.state.require_port_security_disabled
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
                name=f"{self.id.lower()}-vm-w-{worker_number}",
                image=VmResourceImage(name=BASE_IMAGE_WORKER, url=BASE_IMAGE_URL),
                flavor=area.worker_flavors,
                username="ubuntu",
                password=self.state.password,
                management_network=area.mgmt_net,
                additional_networks=area.additional_networks,
                require_port_security_disabled=self.state.require_port_security_disabled
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
        if area.additional_networks:
            for additional_network in area.additional_networks:
                if additional_network not in self.state.attached_networks:
                    self.state.attached_networks.append(additional_network)
        if area not in self.state.area_list:
            self.state.area_list.append(area)

    def setup_load_balancer_pool(self):
        """
        Creates the load balancer pool to be used by MetalLB.
        By default, TODO

        """
        # Reserve a range of IP in the service net
        lb_area_list: List[K8sLoadBalancerPoolArea] = []

        for key, value in self.state.load_balancer_ips_area.items():
            # All workers in the area will be hosts that announce the LB pool
            hostnames = [vm.name.lower() for vm in self.state.vm_workers if vm.area == int(key)]
            # If the controller is in the area add it
            if self.state.vm_master.area == int(key):
                hostnames.append(self.state.vm_master.name.lower())
            if len(hostnames) == 0:
                hostnames = None
            lb_area = K8sLoadBalancerPoolArea(pool_name=f"{self.id.lower()}-area1", ip_list=value, host_names=hostnames)
            lb_area_list.append(lb_area)

        self.state.load_balancer_pools = lb_area_list

    def day0conf(self, configure_master: bool = False):
        """
        Perform Day 0 configuration for master or worker.
        Args:
            configure_master: if the master has to be configured. This value is False for day2 request (Master has been already configured), while it should be true only on creation.
        """
        if configure_master:
            # Configuring the master node
            master_conf = self.state.day_0_master_configurator
            master_conf.configure_master(master_ip=self.state.vm_master.get_management_interface().fixed.ip,
                                         master_external_ip=self.state.vm_master.access_ip,
                                         pod_network_cidr=self.state.pod_network_cidr,
                                         k8s_service_cidr=self.state.pod_service_cidr)
            master_result = self.provider.configure_vm(master_conf)

            # REGISTERING GENERATED VALUES FROM MASTER CONFIGURATION
            self.state.master_key_add_worker = re.sub(r"[0-9]+.[0-9]+.[0-9]+.[0-9]+:6443", f"{self.state.vm_master.access_ip}:6443", master_result['kubernetes_join_command']['stdout'])  #
            # If there is a floating IP, we need to use this one in the k8s config file (instead of the internal one)
            self.state.master_credentials = re.sub(r"https://(.*):6443", f"https://{self.state.vm_master.access_ip}:6443", master_result['credentials_file']['stdout'])

        # Configuring ONLY worker nodes that have not yet been configured and then removing from the list
        for configurator in self.state.day_0_workers_configurators_tobe_exec:
            configurator.configure_worker(self.state.master_key_add_worker, self.state.master_credentials)
            self.provider.configure_vm(configurator)

        self.state.day_0_workers_configurators_tobe_exec = []

    def fix_dns_problem(self):
        """
        Internal .maas domain is SOMETIMES not resolved by the internal K8S DNS. This function fixes the problem.
        """
        client_config = get_k8s_config_from_file_content(self.state.master_credentials)
        # Get the Core DNS configmap
        config_map = get_config_map(client_config, "kube-system", "coredns")
        # Extract data
        dns_config_file_content: str = config_map.data['Corefile']
        # Add internal DNS to solve maas domain
        dns_config_file_content += "maas:53 {\n    forward . 192.168.17.25\n}\n"
        config_map.data['Corefile'] = dns_config_file_content
        # Patch the config map
        result = patch_config_map(client_config, "coredns", "kube-system", config_map)
        return result

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
        plug_list.append(K8sPluginName.CADVISOR)

        # Get the k8s pod network cidr
        pod_network_cidr = get_k8s_cidr_info(client_config)
        # Create additional data for plugins (lbpool and cidr)
        add_data = K8sPluginAdditionalData(areas=self.state.load_balancer_pools, pod_network_cidr=pod_network_cidr, cadvisor_node_port=self.state.cadvisor_node_port)

        install_plugins_to_cluster(kube_client_config=client_config, plugins_to_install=plug_list,
                                   template_fill_data=add_data, cluster_id=self.base_model.id)

    @day2_function("/add_node", [HttpRequestType.POST])
    def add_worker(self, model: K8sAddNodeModel):
        """
        Adds a kubernetes node to a blueprint generated K8S cluster.

        Elaborates the request to add WORKER nodes to (multiple) area(s).
        First it deploys the workers, then it configures them.
        Args:
            model: The request containing information about workers to be added and in witch area
        """
        area: K8sAreaDeployment
        for area in model.areas:
            # THERE ARE NO MASTER AREAS in the request -> THERE IS A CONSTRAINT IN THE REQUEST MODEL
            self.deploy_area(area)

        self.day0conf(configure_master=False)

    @day2_function("/del_workers", [HttpRequestType.DELETE])
    def del_workers(self, model: K8sDelNodeModel):
        """
        Destroy a worker from a blueprint generated K8S cluster. The number of nodes (controller/master + workers) cannot be lower than 2.
        Args:
            model: The list of VM names to be deleted from the K8S cluster
        """
        vm_to_be_destroyed = []  # The list of VM to be destroyed (After the check that exist)

        if self.state.vm_master.name in model.node_names:  # If one of the nodes to be removed is the MASTER, let's remove it
            model.node_names.pop(model.node_names.index(self.state.vm_master.name)) # Removing the master node from the list and logging error
            self.logger.error(f"Master node {self.state.vm_master.id} cannot be deleted from cluster {self.id}. Moving to next nodes to be deleted")
        if len(self.state.vm_workers) <= 1:  # If the number of workers will be zero. STOP
            self.logger.error(
                f"The number of workers cannot be lower than 1. Pods are scheduled only on workers node, there will be no schedule.")
            return

        dayNconf = VmK8sDayNConfigurator(vm_resource=self.state.vm_master)  # Removing the nodes on a cluster requires actions performed on the master node.
        for node in model.node_names:
            target_vm = [vm for vm in self.state.vm_workers if vm.name == node]  # Checking that the node to be removed EXISTS
            if len(target_vm) >= 1:
                dayNconf.delete_node(target_vm[0].get_name_k8s_format())  # Adding the action to remove it from the cmaster/controller.
                vm_to_be_destroyed.append(target_vm[0])  # Appending the VM to be deleted.
            else:
                self.logger.error(f"Node >{node}< has not been found, cannot be deleted from cluster {self.id}. Moving to next nodes to be deleted")

        self.provider.configure_vm(dayNconf)  # Removing from the cluster every VM to be deleted before it will be destroyed (Nodes is removed from k8s cluster by master configurator)

        for vm in vm_to_be_destroyed:  # Destroying every VM to be removed from the cluster
            self.provider.destroy_vm(vm)  # Delete the VM from the provider
            self.deregister_resource(vm)  # Delete from registered resources
            # Destroying configurator and releasing the worker number, deregister worker resources from the state
            conf_to_be_deregistered = self.state.remove_worker(vm)
            for configurator in conf_to_be_deregistered:
                self.deregister_resource(configurator)

    @day2_function("/install_karmada", [HttpRequestType.POST])
    def configure_karmada(self, model: KarmadaInstallModel):
        """
        Install and configure submariner and Karmada on an existing blueprint generated K8S cluster.
        Creates a configurator that installs and configures submarine and karmada.
        """
        master_conf = self.state.day_0_master_configurator
        master_conf.install_karmada(model)
        self.provider.configure_vm(master_conf)

    @day2_function("/install_istio", [HttpRequestType.POST])
    def install_istio(self, msg):
        """
        Creates a configurator that installs and configures submarine and istio.
        """
        master_conf = self.state.day_0_master_configurator
        master_conf.install_istio()
        master_result = self.provider.configure_vm(master_conf)
        # TODO expose prometheus to external using nodeport

    def destroy(self):
        """
        Destroy the blueprints. Calls super destroy that destroy VMs and configurators.
        Then release all the reserved resources in the topology.
        """
        if self.state.topology_onboarded:
            try:
                build_topology().del_k8scluster(self.id)
            except ValueError:
                self.logger.error(f"Could not delete K8S cluster {self.id} from topology: NOT FOUND")
            except TopoK8SHasBlueprintException as e:
                self.logger.error(f"Blueprint {self.id} will not be destroyed")
                raise e
        super().destroy()
        # Remove reserved IP range
        build_topology().release_ranges(self.id)  # Remove all reserved ranges in the networks
        # If it was onboarded on the topology (as a usable k8s cluster), remove it.

    def to_dict(self, detailed: bool) -> dict:
        """
        OVERRIDE
        Return a dictionary representation of the K8S blueprint instance.
        Use the father function to generate the dict, if not detailed, add the node list.

        Args:
            detailed: Return the same content saved in the database containing all the details of the blueprint.

        Returns:

        """
        if detailed:
            return super().to_dict(detailed)
        else:
            base_dict = super().to_dict(detailed)
            if self.base_model.state.vm_master:
                ip_list = [f"Controller {self.base_model.state.vm_master.name}: {self.base_model.state.vm_master.access_ip}"]
                ip_list.extend([f"Worker {vm.name}: {vm.access_ip}" for vm in self.base_model.state.vm_workers])
                base_dict['node_list'] = ip_list
            return base_dict
