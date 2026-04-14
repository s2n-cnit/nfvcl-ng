import json
import copy
from ipaddress import ip_network
from typing import Optional, List, Dict

from nfvcl.blueprints_ng.modules.open5gs import open5gs_default_upf_config
from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import DeployedUPFInfo
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf_vm import Generic5GUPFVMBlueprintNGState, Generic5GUPFVMBlueprintNG
from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_common.utils.blue_utils import rel_path, yaml
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address
from nfvcl_core_models.resources import VmResourceAnsibleConfiguration, VmResource, VmResourceImage, VmResourceFlavor
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo
from nfvcl_models.blueprint_ng.open5gs.upf import Open5gsUpfConfig, PcfpServerItem, GtpuServerItem

OPEN5GS_UPF_BLUE_TYPE = "open5gs_upf"


class Open5GsUpfConfigurator(VmResourceAnsibleConfiguration):
    upf_id: Optional[str] = Field(default=None)
    ipv4_subnet: Optional[str] = Field(default=None)
    ipv4_address: Optional[str] = Field(default=None)
    upf_conf: Optional[str] = Field(default=None)
    gnb_cidr: Optional[str] = Field(default=None)
    n3_gateway: Optional[str] = Field(default=None)
    n6_gateway: Optional[str] = Field(default=None)
    n6: Optional[str] = Field(default=False)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook Open5GsUpfConfigurator")

        ansible_builder.set_var("upf_id", self.upf_id)
        ansible_builder.set_var("ipv4_subnet", self.ipv4_subnet)
        ansible_builder.set_var("ipv4_address", self.ipv4_address)
        ansible_builder.set_var("upf_conf", self.upf_conf)
        ansible_builder.set_var("gnb_cidr", self.gnb_cidr)
        ansible_builder.set_var("n3_gateway", self.n3_gateway)
        ansible_builder.set_var("n6_gateway", self.n6_gateway)
        ansible_builder.set_var("n6", self.n6)

        ansible_builder.add_template_task(rel_path("start.sh.jinja2"), "/root/Open5GS_UPF/start.sh")
        ansible_builder.add_template_task(rel_path("stop.sh.jinja2"), "/root/Open5GS_UPF/stop.sh")
        ansible_builder.add_template_task(rel_path("open5gs_upf.service.jinja2"), "/etc/systemd/system/open5gs_upf.service")

        ansible_builder.add_template_task(rel_path("compose.jinja2"), "/root/Open5GS_UPF/compose.yaml")
        ansible_builder.add_template_task(rel_path("upf_conf.jinja2"), "/root/Open5GS_UPF/config/upf.yaml")

        ansible_builder.add_template_task(rel_path("upf_forward.sh.jinja2"), "/opt/upf_forward.sh")
        ansible_builder.add_template_task(rel_path("upf_forward.service.jinja2"), "/etc/systemd/system/upf_forward.service")
        ansible_builder.add_shell_task("systemctl daemon-reload")

        ansible_builder.add_service_task("upf_forward", ServiceState.STARTED, True)
        ansible_builder.add_service_task("open5gs_upf", ServiceState.RESTARTED, True)

        # Build the playbook and return it
        return ansible_builder.build()


class Open5GsUpfBlueprintNGState(Generic5GUPFVMBlueprintNGState):
    vm_configurators: Dict[str, Open5GsUpfConfigurator] = Field(default_factory=dict)
    upf_conf: Dict[str, Open5gsUpfConfig] = Field(default_factory=dict)
    currently_deployed_dnns: Dict[str, DeployedUPFInfo] = Field(default_factory=dict)


@blueprint_type(OPEN5GS_UPF_BLUE_TYPE)
class Open5GsUpf(Generic5GUPFVMBlueprintNG[Open5GsUpfBlueprintNGState, UPFBlueCreateModel]):

    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFVMBlueprintNGState] = Open5GsUpfBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_upf(self):
        self.logger.info("Starting creation of Open5Gs blueprint")
        self.update_deployments()

    def update_upf(self):
        """
        Update the UPF configuration
        """
        self.logger.info("Starting update of Open5Gs blueprint")
        self.update_deployments()

    def update_deployments(self):
        dnns_to_deploy: List[str] = []
        for slice in self.state.current_config.slices:
            for dnnslice in slice.dnn_list:
                dnns_to_deploy.append(dnnslice.dnn)
        for dnn in set(dnns_to_deploy):
            if dnn not in self.state.currently_deployed_dnns:
                deployed_info = self.deploy_upf_vm(dnn)
                self.state.upf_list.append(deployed_info)
                self.state.currently_deployed_dnns[dnn] = deployed_info
            else:
                # Reconfigure existing VMs (e.g. when nrf_ip is provided in a subsequent update)
                self.reconfigure_upf_vm(dnn)
        dnn_to_undeploy = set(self.state.currently_deployed_dnns) - set(dnns_to_deploy)
        for dnn in set(dnn_to_undeploy):
            deployed_info = self.undeploy_upf_vm(dnn)
            self.state.upf_list.remove(deployed_info)
            del self.state.currently_deployed_dnns[dnn]

    def deploy_upf_vm(self, dnn: str) -> DeployedUPFInfo:
        upf_vm = VmResource(
            area=self.state.current_config.area_id,
            name=f"{self.id}_{self.state.current_config.area_id}_OPEN5GS_UPF_{dnn}",
            image=VmResourceImage(name="Open5GSUPF-v2.7.6-ubuntu2204", url="https://images.tnt-lab.unige.it/open5gsupf/open5gsupf-v2.7.6-ubuntu2204.qcow2"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="ubuntu",
            management_network=self.state.current_config.networks.mgt.net_name,
            additional_networks=[self.state.current_config.networks.n4.net_name, self.state.current_config.networks.n3.net_name, self.state.current_config.networks.n6.net_name],
            require_port_security_disabled=True
        )
        self.register_resource(upf_vm)
        self.provider.create_vm(upf_vm)

        if dnn not in self.state.upf_conf:
            self.state.upf_conf[dnn] = copy.deepcopy(open5gs_default_upf_config.default_upf_config)

        self.state.upf_conf[dnn].upf.pfcp.server.clear()
        self.state.upf_conf[dnn].upf.gtpu.server.clear()
        self.state.upf_conf[dnn].upf.session.clear()

        pcfp = PcfpServerItem(
            address=upf_vm.network_interfaces[self.create_config.networks.n4.net_name][0].fixed.ip
        )
        self.state.upf_conf[dnn].upf.pfcp.server.append(pcfp)
        self.state.upf_conf[dnn].upf.pfcp.node_id = upf_vm.network_interfaces[self.create_config.networks.n4.net_name][0].fixed.ip

        gtpu = GtpuServerItem(
            address=upf_vm.network_interfaces[self.create_config.networks.n3.net_name][0].fixed.ip
        )
        self.state.upf_conf[dnn].upf.gtpu.server.append(gtpu)

        for _slice in self.state.current_config.slices:
            for dnnslice in _slice.dnn_list:
                if dnnslice.dnn == dnn:
                    self.state.upf_conf[dnn].add_session(
                        dnn=dnn,
                        cidr=dnnslice.cidr
                    )

        upf_conf_yaml = yaml.dump(json.loads(self.state.upf_conf[dnn].model_dump_json(by_alias=True)))

        subnet = self.get_dnn_ip_pool(dnn)

        network = ip_network(subnet)
        ip = list(network.hosts())[0].exploded
        mask = network.prefixlen

        upf_vm_configurator = Open5GsUpfConfigurator(
            vm_resource=upf_vm,
            upf_id=dnn,
            ipv4_subnet=subnet,
            ipv4_address=f"{ip}/{mask}",
            upf_conf=upf_conf_yaml,
            gnb_cidr=self.state.current_config.gnb_cidr.exploded,
            n3_gateway=self.state.current_config.n3_gateway_ip.exploded,
            n6_gateway=self.state.current_config.n6_gateway_ip.exploded,
            n6=upf_vm.network_interfaces[self.state.current_config.networks.n6.net_name][0].fixed.interface_name
        )

        self.register_resource(upf_vm_configurator)
        self.provider.configure_vm(upf_vm_configurator)

        self.state.vm_resources[upf_vm.id] = upf_vm
        self.state.vm_configurators[upf_vm_configurator.id] = upf_vm_configurator

        return DeployedUPFInfo(
            area=self.state.current_config.area_id,
            served_slices=self.get_slices_for_dnn(dnn),
            vm_resource_id=upf_vm.id,
            vm_configurator_id=upf_vm_configurator.id,
            fqdn=f"upf-{dnn}",
            network_info=UPFNetworkInfo(
                n4_cidr=SerializableIPv4Network(upf_vm.network_interfaces[self.create_config.networks.n4.net_name][0].fixed.cidr),
                n3_cidr=SerializableIPv4Network(upf_vm.network_interfaces[self.create_config.networks.n3.net_name][0].fixed.cidr),
                n6_cidr=SerializableIPv4Network(upf_vm.network_interfaces[self.create_config.networks.n6.net_name][0].fixed.cidr),
                n4_ip=SerializableIPv4Address(upf_vm.network_interfaces[self.create_config.networks.n4.net_name][0].fixed.ip),
                n3_ip=SerializableIPv4Address(upf_vm.network_interfaces[self.create_config.networks.n3.net_name][0].fixed.ip),
                n6_ip=SerializableIPv4Address(upf_vm.network_interfaces[self.create_config.networks.n6.net_name][0].fixed.ip)
            )
        )

    def reconfigure_upf_vm(self, dnn: str):
        """
        Reconfigure an already deployed UPF VM, updating the NRF registration and other settings.
        This is called during updates when the DNN already has a deployed VM.
        """
        self.logger.info(f"Reconfiguring UPF VM for DNN {dnn}")
        upf_info = self.state.currently_deployed_dnns[dnn]
        upf_vm_configurator = self.state.vm_configurators[upf_info.vm_configurator_id]

        config = self.state.upf_conf[dnn]
        for _slice in self.state.current_config.slices:
            for dnnslice in _slice.dnn_list:
                if dnnslice.dnn == dnn:
                    config.add_session(
                        dnn=dnn,
                        cidr=dnnslice.cidr
                    )

        upf_conf_yaml = yaml.dump(json.loads(self.state.upf_conf[dnn].model_dump_json(by_alias=True)))
        upf_vm_configurator.upf_conf = upf_conf_yaml
        self.provider.configure_vm(upf_vm_configurator)

        upf_info.served_slices = self.get_slices_for_dnn(dnn)

    def undeploy_upf_vm(self, dnn: str):
        upf_info = self.state.currently_deployed_dnns[dnn]

        self.provider.destroy_vm(self.state.vm_resources[upf_info.vm_resource_id])

        self.deregister_resource_by_id(upf_info.vm_resource_id)
        self.deregister_resource_by_id(upf_info.vm_configurator_id)
        del self.state.vm_resources[upf_info.vm_resource_id]
        del self.state.vm_configurators[upf_info.vm_configurator_id]

        return upf_info
