import textwrap
from ipaddress import IPv4Address
from typing import List

from ruamel.yaml.scalarstring import LiteralScalarString
from blueprints_ng.utils import rel_path
from blueprints_ng.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from blueprints_ng.resources import VmResourceAnsibleConfiguration
from models.blueprint_ng.k8s.k8s_rest_models import KarmadaInstallModel

DUMMY_NET_POOL_START_IP = "10.252.252.20"
DUMMY_NET_VM_START_IP = "10.252.252.1"

class VmK8sDay0Configurator(VmResourceAnsibleConfiguration):
    """
    This is the configurator for day0 of kubernetes nodes (master and workers)
    """
    _ansible_builder: AnsiblePlaybookBuilder # _ in front of the name, so it is not serialized
    vm_number: int

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string.
        """

        return self._ansible_builder.build()

    def __configure_common(self, vm_dummy_ipaddress: str, dummy_ip_address_list: List[str] =None) -> None:
        # Copy the script for dummynet on the machine
        if dummy_ip_address_list is None:
            dummy_ip_address_list = []
        self._ansible_builder.set_var("pool_ipaddresses", dummy_ip_address_list)
        self._ansible_builder.set_var("vm_ipaddress", vm_dummy_ipaddress)

        self._ansible_builder.add_template_task(rel_path("services/dummynet.sh"), "/usr/bin/dummynet.sh")
        # Copy the service to start dummynet creation on startup
        self._ansible_builder.add_copy_task(rel_path("services/dummy-network.service"), "/etc/systemd/system/dummy-network.service", remote_src=False, mode=0o644)
        self._ansible_builder.add_service_task("dummy-network", service_state=ServiceState.STARTED)

    def configure_master(self, master_ip: str, master_external_ip: str, pod_network_cidr: str, k8s_service_cidr: str, dummy_ip_address_list: List[str]):
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Master Day0Configurator")

        master_dummy_ip = IPv4Address(DUMMY_NET_VM_START_IP).exploded # The master has the first IP (+0)
        self.__configure_common(master_dummy_ip, dummy_ip_address_list)
        # Using the playbook to configure the master
        self._ansible_builder.add_tasks_from_file(rel_path("playbooks/kubernetes_master_day0_1.yaml"))

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

        worker_dummy_ip = (IPv4Address(DUMMY_NET_VM_START_IP)+1+self.vm_number).exploded
        self.__configure_common(worker_dummy_ip)

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
