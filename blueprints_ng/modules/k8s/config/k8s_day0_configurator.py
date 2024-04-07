import textwrap
from ipaddress import IPv4Address
from typing import List
from ruamel.yaml.scalarstring import LiteralScalarString
from blueprints_ng.utils import rel_path
from blueprints_ng.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from blueprints_ng.resources import VmResourceAnsibleConfiguration
from models.blueprint_ng.k8s.k8s_rest_models import KarmadaInstallModel

class VmK8sDay0Configurator(VmResourceAnsibleConfiguration):
    """
    This is the configurator for day0 of kubernetes nodes (master and workers)
    """
    _ansible_builder: AnsiblePlaybookBuilder = AnsiblePlaybookBuilder("K8s Master Day0Configurator") # _ in front of the name, so it is not serialized !!!
    vm_number: int # The number is used to enumerate the workers since they can be added and removed. This allows IPs and VM names circular usage.

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string.
        """
        return self._ansible_builder.build()

    def __configure_common(self, vm_dummy_ipaddress: str, dummy_ip_address_list: List[str] =None) -> None:
        """
        Add task to the ansible builder that creates and enable a service on the target machine. This service is a
        'one shot' service, executed on startup that creates a dummy network interface on the target machine.
        To this dummy network a list of ip addresses are assigned. This list of ip addresses CAN be used (depends on
        the blueprint creation request) to expose k8s services.
        Args:
            vm_dummy_ipaddress: The dummy IP reserved for the machine
            dummy_ip_address_list: The dummy IP list that will (if required) used to expose services.
        """
        # Copy the script for dummynet on the machine
        if dummy_ip_address_list is None:
            dummy_ip_address_list = []
        self._ansible_builder.set_var("pool_ipaddresses", dummy_ip_address_list)
        self._ansible_builder.set_var("vm_ipaddress", vm_dummy_ipaddress)
        # Copy the script to be executed for creating the dummynet
        self._ansible_builder.add_template_task(rel_path("services/dummynet.sh"), "/usr/bin/dummynet.sh")
        # Copy the service to start dummynet creation on startup (using the previous script)
        self._ansible_builder.add_copy_task(rel_path("services/dummy-network.service"), "/etc/systemd/system/dummy-network.service", remote_src=False, mode=0o644)
        self._ansible_builder.add_service_task("dummy-network", service_state=ServiceState.STARTED)

    def configure_master(self, master_ip: str, master_external_ip: str, pod_network_cidr: str, k8s_service_cidr: str, dummy_ip_address_list: List[str], master_dummy_ip_s: str):
        """
        This function is creating ansible tasks for configuring the master node of a K8S cluster, in order:
        Configures dummy network (see __configure_common).
        Initialize the cluster.
        Copy the config for kubectl to user root and ubuntu.
        Retrieving config for kubectl in the worker nodes, retrieving the joining command for workers.
        Args:
            master_ip: The IP address of the master node (internal)
            master_external_ip: The IP address of the master node (external). IT CAN COINCIDE WITH master_ip if there is no floating IP.
            pod_network_cidr: The CIDR to be used for pods
            k8s_service_cidr: The CIDR to be used for k8s services
            dummy_ip_address_list: external services IPs to be assigned at the dummy network interface for the controller
            master_dummy_ip_s: The IP address of the dummy network reserved for the master node.
        """
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Master Day0Configurator") # Reset the playbook
        self.__configure_common(master_dummy_ip_s, dummy_ip_address_list)
        # Using the playbook to configure the master
        self._ansible_builder.add_tasks_from_file(rel_path("playbooks/kubernetes_master_day0_1.yaml"))
        # Set the playbook variables for the master node
        self._ansible_builder.set_var("pod_network_cidr", pod_network_cidr)
        self._ansible_builder.set_var("k8s_master_ip", master_ip)
        self._ansible_builder.set_var("k8s_master_external_ip", master_external_ip)
        self._ansible_builder.set_var("k8s_service_cidr", k8s_service_cidr)
        # Adding variables to be collected on playbook execution
        self._ansible_builder.add_gather_var_task("credentials_file")
        self._ansible_builder.add_gather_var_task("kubernetes_join_command")


    def configure_worker(self, join_command: str, credentials_file: str, master_dummy_ip_s: str):
        """
        This function is creating ansible tasks for configuring a worker node of a K8S cluster, in order:
        Configures dummy network (see __configure_common).
        Configure the worker (join command, kubectl config with credential file).
        Args:
            join_command: The join command retrieved from the master node
            credentials_file: The config file (admin.conf) retrieved from the master node that is used to configure kubectl on worker node
            master_dummy_ip_s: The IP address of the master node to be used as reference to assign worker nodes IPs
        """
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Worker Day0Configurator") # Reset the playbook

        # The worker IP is sequential to the master (e.g. 192.138.0.1) -> workers [192.138.0.2, 192.138.0.3, ..., 192.138.0.N)
        worker_dummy_ip = (IPv4Address(master_dummy_ip_s)+1+self.vm_number).exploded
        self.__configure_common(worker_dummy_ip)

        self._ansible_builder.add_tasks_from_file(rel_path("playbooks/kubernetes_worker_day0.yaml"))
        # Set the playbook variables
        self._ansible_builder.set_var("join_command", join_command) # The command to join the cluster
        self._ansible_builder.set_var("credentials_file", LiteralScalarString(textwrap.dedent(credentials_file))) # Credential file to be used for k8s management in workers
        self._ansible_builder.add_gather_var_task("joined_or_not")

    def install_karmada(self, request: KarmadaInstallModel):
        """
        Creates tasks for the ansible builder that install and configure karmada and submariner
        Args:
            request: the request containing data for karmada and submariner configuration.
        """
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Master Day0 Karmada")
        # Using the playbook to configure karmada and submariner
        self._ansible_builder.add_tasks_from_file(rel_path("playbooks/kubernetes_master_inst_karmada.yaml"))
        # Set the playbook variables for karmada, submariner
        self._ansible_builder.set_var("cluster_id", request.cluster_id)
        self._ansible_builder.set_var("kube_config_location", request.kube_config_location)
        self._ansible_builder.set_var("submariner_broker", request.submariner_broker)
        self._ansible_builder.set_var("karmada_control_plane", request.karmada_control_plane)
        self._ansible_builder.set_var("karmada_token", request.karmada_token)
        self._ansible_builder.set_var("discovery_token_hash", request.discovery_token_hash)
