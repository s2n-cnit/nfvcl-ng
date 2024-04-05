from blueprints_ng.utils import rel_path
from blueprints_ng.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from blueprints_ng.resources import VmResourceAnsibleConfiguration
from models.blueprint_ng.k8s.k8s_rest_models import CreateVxLanModel
from netaddr import IPNetwork
from utils.util import render_file_jinja2_to_str


class VmK8sDay2Configurator(VmResourceAnsibleConfiguration):
    """
    This is the configurator for day0 of kubernetes nodes (master and workers)
    """
    _ansible_builder: AnsiblePlaybookBuilder  # _ in front of the name, so it is not serialized

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string.
        """

        return self._ansible_builder.build()

    def configure_vxlan(self, vxlan_request: CreateVxLanModel, server_floating: str = None) -> str:
        """
        Create and configure a service that creates a VXLAN on the ansible target machine.
        Args:
            vxlan_request: The request containing parameters to create a VXLAN on the machine
            server_floating: If the server has a floating IP, the client will see this IP address. If None then it will use the internal IP to build the client config.

        Returns:
            A string containing the commands to be executed on the client machine to be connected to the VXLAN
        """
        self._ansible_builder = AnsiblePlaybookBuilder("K8s Master Day0Configurator")

        ip_net = IPNetwork(vxlan_request.vxlan_server_int_cidr)
        vxlan_server_int_ip = str(ip_net[1])
        vxlan_client_int_ip = str(ip_net[2])

        vars = {
            "vx_name": vxlan_request.vx_name,
            "vxid": vxlan_request.vxid,
            "vx_client_ip": vxlan_request.vx_client_ip,
            "vx_server_ip": vxlan_request.vx_server_ip,
            "vx_server_floating_ip": server_floating,
            "vx_server_ext_device": vxlan_request.vx_server_ext_device,
            "vx_server_ext_port": vxlan_request.vx_server_ext_port,
            "vxlan_server_int_ip": vxlan_server_int_ip,
            "vxlan_client_int_ip": vxlan_client_int_ip
            }
        self._ansible_builder.set_vars(vars)

        # Add the script that create at startup the vxlan
        self._ansible_builder.add_template_task(rel_path("services/vxlank8s.sh"), f"/usr/bin/vxlank8s{vxlan_request.vx_name}.sh")
        # Create the service that run the script at startup
        self._ansible_builder.add_template_task(rel_path("services/vxlan.service"), f"/etc/systemd/system/vxlan{vxlan_request.vx_name}.service")

        # Enable and start the service
        self._ansible_builder.add_service_task(f"vxlan{vxlan_request.vx_name}", service_state=ServiceState.STARTED)

        # Rendering the template to be returned to the request
        return render_file_jinja2_to_str(rel_path("services/vxlank8s-client.sh"), vars)
