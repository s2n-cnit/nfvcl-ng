import textwrap

from ruamel.yaml.scalarstring import LiteralScalarString

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_core_models.network.ipam_models import SerializableIPv4Network
from nfvcl_core_models.resources import VmResourceAnsibleConfiguration
from nfvcl_models.blueprint_ng.k8s.k8s_rest_models import KarmadaInstallModel
from nfvcl_common.utils.blue_utils import rel_path


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

    def set_blueprint_id(self, blueprint_id: str) -> None:
        self.blueprint_id = blueprint_id

    def configure_master(self, master_ip: str, master_external_ip: str, pod_network_cidr: SerializableIPv4Network, k8s_service_cidr: SerializableIPv4Network) -> None:
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
        """
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Master Day0Configurator") # Reset the playbook
        # Using the playbook to configure the master
        self._ansible_builder.add_tasks_from_file(rel_path("playbooks/k8s_master_day0.yaml"))
        # Set the playbook variables for the master node
        self._ansible_builder.set_var("pod_network_cidr", str(pod_network_cidr))
        self._ansible_builder.set_var("k8s_master_ip", master_ip)
        self._ansible_builder.set_var("k8s_master_external_ip", master_external_ip)
        self._ansible_builder.set_var("k8s_service_cidr", str(k8s_service_cidr))
        # Adding variables to be collected on playbook execution
        self._ansible_builder.add_gather_var_task("credentials_file")
        self._ansible_builder.add_gather_var_task("kubernetes_join_command")


    def configure_worker(self, join_command: str, credentials_file: str):
        """
        This function is creating ansible tasks for configuring a worker node of a K8S cluster, in order:
        Configures dummy network (see __configure_common).
        Configure the worker (join command, kubectl config with credential file).
        Args:
            join_command: The join command retrieved from the master node
            credentials_file: The config file (admin.conf) retrieved from the master node that is used to configure kubectl on worker node
        """
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Worker Day0Configurator") # Reset the playbook

        self._ansible_builder.add_tasks_from_file(rel_path("playbooks/k8s_worker_day0.yaml"))
        # Set the playbook variables
        self._ansible_builder.set_var("join_command", join_command) # The command to join the cluster
        self._ansible_builder.set_var("credentials_file", LiteralScalarString(textwrap.dedent(credentials_file)))  # Credential file to be used for k8s management in workers
        self._ansible_builder.add_gather_var_task("joined_or_not")


    def configure_mirrors(self, mirrors: dict[str, str]):
        """
        """
        self._ansible_builder.set_var("k8s_mirrors", mirrors)
        self._ansible_builder.add_render_and_execute_template_task(rel_path("playbooks/k8s_set_mirrors.j2"), {"k8s_mirrors": mirrors}, rendered_file_prefix=self.vm_resource.name)
        self._ansible_builder.add_service_task("containerd", ServiceState.RESTARTED, True)

    def install_karmada(self, request: KarmadaInstallModel):
        """
        Creates tasks for the ansible builder that install and configure karmada and submariner
        Args:
            request: the request containing data for karmada and submariner configuration.
        """
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Master Day0 Karmada")
        # Using the playbook to configure karmada and submariner
        self._ansible_builder.add_tasks_from_file(rel_path("playbooks/k8s_master_karmada.yaml"))
        # Set the playbook variables for karmada, submariner
        self._ansible_builder.set_var("cluster_id", request.cluster_id)
        self._ansible_builder.set_var("kube_config_location", request.kube_config_location)
        self._ansible_builder.set_var("submariner_broker", request.submariner_broker)
        self._ansible_builder.set_var("karmada_control_plane", request.karmada_control_plane)
        self._ansible_builder.set_var("karmada_token", request.karmada_token)
        self._ansible_builder.set_var("discovery_token_hash", request.discovery_token_hash)

    def install_istio(self):
        """
        Creates tasks for the ansible builder that install and configure istio
        """
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Master Day0 Istio")
        # Using the playbook to configure karmada and submariner
        self._ansible_builder.add_tasks_from_file(rel_path("playbooks/k8s_master_istio.yaml"))
