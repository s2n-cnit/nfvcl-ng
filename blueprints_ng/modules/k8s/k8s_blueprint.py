from typing import Optional, List
import re
from models.k8s.common_k8s_model import Cni, LBPool
from models.k8s.plugin_k8s_model import K8sPluginName, K8sTemplateFillData
from utils.k8s import get_k8s_config_from_file_content, install_plugins_to_cluster, get_k8s_cidr_info
from models.k8s.topology_k8s_model import K8sModel, K8sVersion
from starlette.requests import Request
from topology.topology import Topology, build_topology
from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface
from blueprints_ng.lcm.blueprint_type_manager import declare_blue_type
from blueprints_ng.modules.k8s.config.day0_configurator import VmK8sDay0Configurator
from models.blueprint_ng.k8s.k8s_rest_models import K8sCreateModel, K8sAreaDeployment
from blueprints_ng.resources import VmResource, VmResourceImage
from pydantic import Field
from blueprints_ng.blueprint_ng import BlueprintNGState, BlueprintNG

K8S_BLUE_TYPE = "k8s"
BASE_IMAGE_MASTER = "k8s-base"
BASE_IMAGE_URL = "http://images.tnt-lab.unige.it/k8s/k8s-v0.0.1.qcow2"
BASE_IMAGE_WORKER = "k8s-base"


class K8sBlueprintNGState(BlueprintNGState):
    """

    """
    version: K8sVersion = Field(default=K8sVersion.V1_29) # CRASH
    cni: Cni = Field(default=Cni.flannel)

    pod_network_cidr: str = Field(default="10.254.0.0/16")
    service_cidr: str = Field(default="10.200.0.0/16")
    expose_service_nets: List[str] = Field(default=[])
    progressive_worker_number: int = 0
    master_area: Optional[K8sAreaDeployment] = Field(default=None)
    area_list: List[K8sAreaDeployment] = []
    attached_networks: List[str] = []

    vm_master: Optional[VmResource] = Field(default=None)
    vm_master_configurator: Optional[VmK8sDay0Configurator] = Field(default=None)

    vm_workers: List[VmResource] = []

    day_0_master_configurator: Optional[VmK8sDay0Configurator] = Field(default=None)
    day_0_workers_configurators: List[VmK8sDay0Configurator] = []

    master_key_add_worker: str = Field(default="", description="The master key to be used by a worker to join the k8s cluster")
    master_credentials: str = Field(default="", description="The certificate of the admin, to allow k8s administration")

@declare_blue_type(K8S_BLUE_TYPE)
class K8sBlueprint(BlueprintNG[K8sBlueprintNGState, K8sCreateModel]):
    def __init__(self, blueprint_id: str, provider_type: type[BlueprintNGProviderInterface], state_type: type[BlueprintNGState] = K8sBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, provider_type, state_type)

    def create(self, create_model: K8sCreateModel):
        super().create(create_model)
        self.logger.info(f"Starting creation of K8s blueprint")
        self.state.pod_network_cidr = create_model.pod_network_cidr
        self.state.service_cidr = create_model.service_cidr
        self.state.cni = create_model.cni

        area: K8sAreaDeployment
        for area in create_model.areas:     # In each area we deploy workers and in the core area also the master (there is always a core area containing the master)
            if area.is_master_area:
                self.state.master_area = area
                # Defining Master node. Should be executed only once
                self.state.vm_master = VmResource(
                    area=area.area_id,
                    name=f"{self.id}_VM_K8S_C",
                    image=VmResourceImage(name=BASE_IMAGE_MASTER, url=BASE_IMAGE_URL),
                    flavor=create_model.master_flavors,
                    username="ubuntu",
                    password=create_model.password,
                    management_network=area.mgmt_net,
                    additional_networks=[area.service_net]
                )
                # Registering master node
                self.register_resource(self.state.vm_master)
                # Creating the VM
                self.provider.create_vm(self.state.vm_master)
                # Creating the configurator for the master
                self.state.day_0_master_configurator = VmK8sDay0Configurator(vm_resource=self.state.vm_master)
                self.register_resource(self.state.day_0_master_configurator)

            for worker_replica_num in range(0,area.worker_replicas):
                # Workers of area X
                self.state.progressive_worker_number += 1
                vm = VmResource(
                    area=area.area_id,
                    name=f"{self.id}_VM_W_{self.state.progressive_worker_number}",
                    image=VmResourceImage(name=BASE_IMAGE_WORKER, url=BASE_IMAGE_URL),
                    flavor=area.worker_flavors,
                    username="ubuntu",
                    password=create_model.password,
                    management_network=area.mgmt_net,
                    additional_networks=[area.service_net]
                )
                self.state.vm_workers.append(vm)
                # Registering master node
                self.register_resource(vm)
                # Creating the VM
                self.provider.create_vm(vm)

                configurator = VmK8sDay0Configurator(vm_resource=vm)
                self.state.day_0_workers_configurators.append(configurator)
                self.register_resource(configurator)

            # For each area, we add the service net to be used to expose services (can differ between areas)
            self.state.expose_service_nets.append(area.service_net)

            if area.mgmt_net not in self.state.attached_networks:
                self.state.attached_networks.append(area.mgmt_net)
            if area.service_net not in self.state.attached_networks:
                self.state.attached_networks.append(area.service_net)
            self.state.area_list.append(area)
        self.day0conf(create_model.pod_network_cidr, create_model.service_cidr, create_model.topology_onboard)

        self.install_plugins()


    @classmethod
    def rest_create(cls, msg: K8sCreateModel, request: Request):
        """
        This is needed for FastAPI to work, don't write code here, just changed the msg type to the correct one
        """
        return cls.api_day0_function(msg, request)


    def day0conf(self, pod_net_cidr, service_cidr, topology_onboard: bool):
        # Configuring the master node
        master_conf = self.state.day_0_master_configurator
        master_conf.configure_master(self.state.vm_master.get_management_interface().fixed.ip, self.state.vm_master.access_ip, pod_net_cidr, service_cidr)
        master_result = self.provider.configure_vm(master_conf)

        # REGISTERING GENERATED VALUES FROM MASTER CONFIGURATION
        self.state.master_key_add_worker = master_result['kubernetes_join_command']['stdout'] #
        # If there is a floating IP, we need to use this one in the k8s config file (instead of the internal one)
        self.state.master_credentials = re.sub("https:\/\/(.*):6443", f"https://{self.state.vm_master.access_ip}:6443", master_result['credentials_file']['stdout'])

        # Configuring worker nodes
        for configurator in self.state.day_0_workers_configurators:
            configurator.configure_worker(self.state.master_key_add_worker, self.state.master_credentials)
            worker_result = self.provider.configure_vm(configurator)

        # If required, onboarding the cluster in the topology
        if topology_onboard:
             topo: Topology = build_topology()
             area_list = [item.area_id for item in self.state.area_list]

             k8s_cluster = K8sModel(name=self.id, provided_by="NFVCL", blueprint_ref=self.id, credentials="", vim_name=topo.get_vim_name_from_area_id(self.state.master_area.area_id), # For the constraint on the model, there is always a master area.
                      k8s_version=K8sVersion.V1_29, networks=self.state.attached_networks, areas=area_list, cni="")
             topo.add_k8scluster(k8s_cluster)


    def install_plugins(self):
        """
        Day 2 operation. Install k8s plugins after the cluster has been initialized.
        Suppose that there is NO plugin installed.
        """
        client_config = get_k8s_config_from_file_content(self.state.master_credentials)
        # Build plugin list
        plug_list: List[K8sPluginName] = []

        if self.state.cni == Cni.flannel.value:
            plug_list.append(K8sPluginName.FLANNEL)
        elif self.state.cni == Cni.calico.value:
            plug_list.append(K8sPluginName.CALICO)
        plug_list.append(K8sPluginName.METALLB)
        plug_list.append(K8sPluginName.OPEN_EBS)

        # IP on the management inteface for the workers, the ones mapped with the floating IP if present
        workers_mgt_int = [item.get_management_interface().fixed.ip for item in self.state.vm_workers]

        # Reserve a range of IP in the service net
        ip_for_net_expose_serv = int(20/len(self.state.expose_service_nets)) # For each network used to expose services we assign 20/total IPs # TODO give pool on request
        reserved_pools = []
        for expose_service_net in self.state.expose_service_nets:
            pool = LBPool(net_name=expose_service_net, range_length=ip_for_net_expose_serv)
            res_range = build_topology().reserve_range_lb_pool(pool, self.id) # TODO IP should be reserved in VIM
            # Building IPv4Addresses to validate. Then saving string because obj cannot be serialized.
            pool.ip_start = res_range.start.exploded
            pool.ip_end = res_range.end.exploded
            reserved_pools.append(pool)

        # Get the k8s pod network cidr
        pod_network_cidr = get_k8s_cidr_info(client_config) # TODO TIMEOUT
        # Create additional data for plugins (lbpool and cidr)
        add_data = K8sTemplateFillData(pod_network_cidr=pod_network_cidr, lb_ipaddresses=workers_mgt_int,
                                       lb_pools=reserved_pools)

        install_plugins_to_cluster(kube_client_config=client_config, plugins_to_install=plug_list,
                                   template_fill_data=add_data, cluster_id=self.base_model.id)


    # TODO implement destroy
