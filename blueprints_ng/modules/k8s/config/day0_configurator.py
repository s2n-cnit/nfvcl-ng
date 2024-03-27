import textwrap
from ruamel.yaml.scalarstring import LiteralScalarString
from blueprints_ng.utils import rel_path
from blueprints_ng.ansible_builder import AnsiblePlaybookBuilder
from blueprints_ng.resources import VmResourceAnsibleConfiguration
from models.blueprint_ng.k8s.k8s_rest_models import KarmadaInstallModel


class VmK8sDay0Configurator(VmResourceAnsibleConfiguration):
    """
    This is the configurator for day0 of kubernetes nodes (master and workers)
    """
    _ansible_builder: AnsiblePlaybookBuilder # _ in front of the name, so it is not serialized

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string.
        """

        return self._ansible_builder.build()

    def configure_master(self, master_ip, master_external_ip, pod_network_cidr, k8s_service_cidr):
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Master Day0Configurator")
        # Using the playbook to configure the master
        self._ansible_builder.add_tasks_from_file(rel_path("playbooks/kubernetes_master_day0.yaml"))

        # Set the playbook variables for the master node
        self._ansible_builder.set_var("pod_network_cidr", pod_network_cidr)
        self._ansible_builder.set_var("k8s_master_ip", master_ip)
        self._ansible_builder.set_var("k8s_master_external_ip", master_external_ip)
        self._ansible_builder.set_var("k8s_service_cidr", k8s_service_cidr)

        # Adding variables to be collected on playbook play
        self._ansible_builder.add_gather_var_task("credentials_file")
        self._ansible_builder.add_gather_var_task("kubernetes_join_command")


    def configure_worker(self, join_command, credentials_file):
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Worker Day0Configurator")
        self._ansible_builder.add_tasks_from_file(rel_path("playbooks/kubernetes_worker_day0.yaml"))
        # Set the playbook variables
        self._ansible_builder.set_var("join_command", join_command) # The command to join the cluster
        self._ansible_builder.set_var("credentials_file", LiteralScalarString(textwrap.dedent(credentials_file))) # Credential file to be used for k8s management in workers
        self._ansible_builder.add_gather_var_task("joined_or_not")

    def install_karmada(self, request: KarmadaInstallModel):
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
