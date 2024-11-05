import copy
import json
from typing import Optional

import yaml
from pydantic import Field

from nfvcl.blueprints_ng.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import Generic5GUPFBlueprintNG, Generic5GUPFBlueprintNGState, DeployedUPFInfo
from nfvcl.blueprints_ng.modules.oai import oai_default_upf_config
from nfvcl.blueprints_ng.modules.oai import oai_utils
from nfvcl.blueprints_ng.resources import VmResourceImage, VmResourceFlavor, VmResource, VmResourceAnsibleConfiguration
from nfvcl.blueprints_ng.utils import rel_path
from nfvcl.models.blueprint_ng.core5g.OAI_Models import Upfconfig, Snssai, DnnItem
from nfvcl.models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo
from nfvcl.models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address

OAI_UPF_BLUE_TYPE = "oai_upf"


class OpenAirInterfaceUpfConfigurator(VmResourceAnsibleConfiguration):
    upf_id: Optional[int] = Field(default=None)
    nrf_ipv4_address: Optional[str] = Field(default=None)
    upf_conf: Optional[str] = Field(default=None)
    gnb_cidr: Optional[str] = Field(default=None)
    n3_gateway: Optional[str] = Field(default=None)
    n6_gateway: Optional[str] = Field(default=None)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook OpenAirInterfaceUpfConfigurator")

        ansible_builder.set_var("upf_id", self.upf_id)
        ansible_builder.set_var("nrf_ipv4_address", self.nrf_ipv4_address)
        ansible_builder.set_var("upf_conf", self.upf_conf)

        ansible_builder.set_var("gnb_cidr", self.gnb_cidr)
        ansible_builder.set_var("n3_gateway", self.n3_gateway)
        ansible_builder.set_var("n6_gateway", self.n6_gateway)

        ansible_builder.add_template_task(rel_path("start.sh.jinja2"), "/root/upfConfig/start.sh")
        ansible_builder.add_template_task(rel_path("stop.sh.jinja2"), "/root/upfConfig/stop.sh")
        ansible_builder.add_template_task(rel_path("oai_upf.service.jinja2"), "/etc/systemd/system/oai_upf.service")

        ansible_builder.add_template_task(rel_path("compose.jinja2"), "/root/upfConfig/compose.yaml")
        ansible_builder.add_template_task(rel_path("upf_conf.jinja2"), "/root/upfConfig/conf/basic_nrf_config.yaml")

        ansible_builder.add_template_task(rel_path("upf_forward.sh.jinja2"), "/opt/upf_forward.sh")
        ansible_builder.add_template_task(rel_path("upf_forward.service.jinja2"), "/etc/systemd/system/upf_forward.service")
        ansible_builder.add_shell_task("systemctl daemon-reload")

        ansible_builder.add_service_task("upf_forward", ServiceState.STARTED, True)
        ansible_builder.add_service_task("oai_upf", ServiceState.RESTARTED, True)

        # Build the playbook and return it
        return ansible_builder.build()


class OAIUpfBlueprintNGState(Generic5GUPFBlueprintNGState):
    upf_vm_configurator: Optional[OpenAirInterfaceUpfConfigurator] = Field(default=None)
    upf_conf: Optional[Upfconfig] = Field(default=None)


@blueprint_type(OAI_UPF_BLUE_TYPE)
class OpenAirInterfaceUpf(Generic5GUPFBlueprintNG[OAIUpfBlueprintNGState, UPFBlueCreateModel]):

    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFBlueprintNGState] = OAIUpfBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_upf(self):
        self.logger.info("Starting creation of OpenAirInterfaceUpf blueprint")
        self.state.upf_conf = copy.deepcopy(oai_default_upf_config.default_upf_config.upfconfig)

        # To describe a new VM create a VmResource object and save it in the state
        upf_vm = VmResource(
            area=self.state.current_config.area_id,
            name=f"{self.id}_OAI_UPF_{self.state.current_config.area_id}",
            image=VmResourceImage(name="OpenAirInterfaceUPF_NG", url="https://images.tnt-lab.unige.it/openairinterfaceupf/openairinterfaceupf-v2.0.0.qcow2"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="ubuntu",
            management_network=self.state.current_config.networks.mgt,
            additional_networks=[self.state.current_config.networks.n4, self.state.current_config.networks.n3, self.state.current_config.networks.n6]
        )
        self.register_resource(upf_vm)
        self.provider.create_vm(upf_vm)
        self.state.vm_resources[upf_vm.id] = upf_vm

        self.state.upf_vm_configurator = OpenAirInterfaceUpfConfigurator(vm_resource=upf_vm)
        self.register_resource(self.state.upf_vm_configurator)

        self.update_upf_info()

    def update_upf(self):
        """
        Update the UPF configuration
        """
        # Clearing previous config
        self.state.upf_conf.snssais.clear()
        self.state.upf_conf.upf.upf_info.sNssaiUpfInfoList.clear()
        self.state.upf_conf.dnns.clear()

        upf_vm = next(iter(self.state.vm_resources.values()))

        self.state.upf_conf.nfs.upf.host = f"oai-upf{self.state.current_config.area_id}"
        self.state.upf_conf.nfs.upf.sbi.interface_name = upf_vm.network_interfaces[self.state.current_config.networks.n4][0].fixed.interface_name
        self.state.upf_conf.nfs.upf.n3.interface_name = upf_vm.network_interfaces[self.state.current_config.networks.n3][0].fixed.interface_name
        self.state.upf_conf.nfs.upf.n4.interface_name = upf_vm.network_interfaces[self.state.current_config.networks.n4][0].fixed.interface_name
        self.state.upf_conf.nfs.upf.n6.interface_name = upf_vm.network_interfaces[self.state.current_config.networks.n6][0].fixed.interface_name
        self.state.upf_conf.nfs.upf.n9.interface_name = upf_vm.network_interfaces[self.state.current_config.networks.n4][0].fixed.interface_name
        self.state.upf_conf.upf.remote_n6_gw = self.state.current_config.n6_gateway_ip.exploded

        for new_slice in self.state.current_config.slices:
            new_snssai: Snssai = oai_utils.add_snssai(self.state.upf_conf, new_slice.id, new_slice.type)
            for dnn in new_slice.dnn_list:
                dnn_item = DnnItem(
                    dnn=dnn.name
                )
                # Add DNNS
                oai_utils.add_dnn_dnns(self.state.upf_conf, dnn.name, dnn.cidr)
                oai_utils.add_dnn_snssai_upf_info_list_item(self.state.upf_conf, new_snssai, dnn_item)

        upf_conf_yaml = yaml.dump(json.loads(self.state.upf_conf.model_dump_json(by_alias=True)))

        self.state.upf_vm_configurator.upf_id = self.state.current_config.area_id
        self.state.upf_vm_configurator.nrf_ipv4_address = self.state.current_config.nrf_ip.exploded
        self.state.upf_vm_configurator.upf_conf = upf_conf_yaml

        self.state.upf_vm_configurator.n3_gateway = self.state.current_config.n3_gateway_ip.exploded
        self.state.upf_vm_configurator.n6_gateway = self.state.current_config.n6_gateway_ip.exploded
        self.state.upf_vm_configurator.gnb_cidr = self.state.current_config.gnb_cidr.exploded

        self.provider.configure_vm(self.state.upf_vm_configurator)

        self.update_upf_info()

    def update_upf_info(self):
        upf_vm = next(iter(self.state.vm_resources.values()))

        deployed_upf_info = DeployedUPFInfo(
            area=self.state.current_config.area_id,
            served_slices=self.state.current_config.slices,
            vm_resource_id=upf_vm.id,
            vm_configurator_id=self.state.upf_vm_configurator.id,
            network_info=UPFNetworkInfo(
                n4_cidr=SerializableIPv4Network(upf_vm.network_interfaces[self.state.current_config.networks.n4][0].fixed.cidr),
                n3_cidr=SerializableIPv4Network(upf_vm.network_interfaces[self.state.current_config.networks.n3][0].fixed.cidr),
                n6_cidr=SerializableIPv4Network(upf_vm.network_interfaces[self.state.current_config.networks.n6][0].fixed.cidr),
                n4_ip=SerializableIPv4Address(upf_vm.network_interfaces[self.state.current_config.networks.n4][0].fixed.ip),
                n3_ip=SerializableIPv4Address(upf_vm.network_interfaces[self.state.current_config.networks.n3][0].fixed.ip),
                n6_ip=SerializableIPv4Address(upf_vm.network_interfaces[self.state.current_config.networks.n6][0].fixed.ip)
            )
        )
        self.state.upf_list.clear()
        self.state.upf_list.append(deployed_upf_info)
