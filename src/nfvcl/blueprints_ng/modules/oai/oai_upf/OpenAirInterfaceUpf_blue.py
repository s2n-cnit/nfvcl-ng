import copy
import json
from typing import Optional

import yaml
from pydantic import Field

from nfvcl.models.blueprint_ng.core5g.OAI_Models import Upfconfig, Snssai, DnnItem
from nfvcl.blueprints_ng.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGState
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.oai import oai_default_upf_config
from nfvcl.blueprints_ng.modules.oai import oai_utils
from nfvcl.blueprints_ng.resources import VmResourceImage, VmResourceFlavor, VmResource, VmResourceAnsibleConfiguration
from nfvcl.blueprints_ng.utils import rel_path
from nfvcl.models.blueprint_ng.g5.upf import UPFBlueCreateModel, UpfPayloadModel

OAI_UPF_BLUE_TYPE = "OpenAirInterfaceUpf"


class OpenAirInterfaceUpfConfigurator(VmResourceAnsibleConfiguration):
    """
    This class is an example for an Ansible configurator for a VM

    The fields in this class will be saved to the DB and can be used to customize the configuration at runtime
    """
    upf_id: Optional[int] = Field(default=None)
    nrf_ipv4_address: Optional[str] = Field(default=None)
    upf_conf: Optional[str] = Field(default=None)

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string
        """

        ansible_builder = AnsiblePlaybookBuilder("Playbook OpenAirInterfaceUpfConfigurator")

        ansible_builder.add_template_task(rel_path("compose.jinja2"), "/root/upfConfig/compose.yaml")
        ansible_builder.add_template_task(rel_path("upf_conf.jinja2"), "/root/upfConfig/conf/basic_nrf_config.yaml")

        ansible_builder.add_template_task(rel_path("upf_forward.sh.jinja2"), "/opt/upf_forward.sh")
        ansible_builder.add_template_task(rel_path("upf_forward.service.jinja2"), "/etc/systemd/system/upf_forward.service")
        ansible_builder.add_shell_task("systemctl daemon-reload")
        ansible_builder.add_service_task("upf_forward", ServiceState.STARTED, True)

        ansible_builder.add_tasks_from_file(rel_path("compose.yaml"))

        ansible_builder.set_var("upf_id", self.upf_id)
        ansible_builder.set_var("nrf_ipv4_address", self.nrf_ipv4_address)
        ansible_builder.set_var("upf_conf", self.upf_conf)

        # Build the playbook and return it
        return ansible_builder.build()


class OAIUpfBlueprintNGState(BlueprintNGState):
    """
    This class represent the current state of the blueprint, the data contained in this class will be saved to the DB

    Every Resource should be stored in a variable in this class to be able to access it after the initial creation

    Everything in this class should be serializable by Pydantic

    Every field need to be Optional because the state is created empty
    """
    vm_upf: Optional[VmResource] = Field(default=None)
    vm_upf_configurator: Optional[OpenAirInterfaceUpfConfigurator] = Field(default=None)
    upf_conf: Optional[Upfconfig] = Field(default=None)
    area_id: Optional[int] = Field(default=None)


@blueprint_type(OAI_UPF_BLUE_TYPE)
class OpenAirInterfaceUpf(BlueprintNG[OAIUpfBlueprintNGState, UPFBlueCreateModel]):

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = OAIUpfBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: UPFBlueCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of OpenAirInterfaceUpf blueprint")
        self.state.upf_conf = copy.deepcopy(oai_default_upf_config.default_upf_config.upfconfig)
        self.state.area_id = create_model.area_id

        # To describe a new VM create a VmResource object and save it in the state
        self.state.vm_upf = VmResource(
            area=create_model.area_id,
            name=f"{self.id}_VM_UPF",
            image=VmResourceImage(name="OpenAirInterfaceUPF_NG", url="https://images.tnt-lab.unige.it/openairinterfaceupf/openairinterfaceupf-v2.0.0.qcow2"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="ubuntu",
            management_network=create_model.networks.mgt,
            additional_networks=[create_model.networks.n4, create_model.networks.n3, create_model.networks.n6]
        )
        self.register_resource(self.state.vm_upf)
        self.provider.create_vm(self.state.vm_upf)

        # nets = [create_model.networks.n4, create_model.networks.n3, create_model.networks.n6]
        # additional_nets = list(set(nets).symmetric_difference([create_model.networks.mgt]))
        #
        # for net in additional_nets:
        #     self.provider.attach_net(self.state.vm_upf, net)

        self.state.vm_upf_configurator = OpenAirInterfaceUpfConfigurator(vm_resource=self.state.vm_upf)
        self.register_resource(self.state.vm_upf_configurator)

    def configure(self, upf_config: UpfPayloadModel):
        """
          Configure upf on first boot.
          :return: day2 instruction to configure upf at the first boot.

        Args:
            upf_config:
          """
        res = []
        # Clearing previous config
        self.state.upf_conf.snssais.clear()
        self.state.upf_conf.upf.upf_info.sNssaiUpfInfoList.clear()
        self.state.upf_conf.dnns.clear()

        self.state.upf_conf.nfs.upf.host = f"oai-upf{self.state.area_id}"
        self.state.upf_conf.nfs.upf.sbi.interface_name = self.state.vm_upf.network_interfaces[self.create_config.networks.n4][0].fixed.interface_name
        self.state.upf_conf.nfs.upf.n3.interface_name = self.state.vm_upf.network_interfaces[self.create_config.networks.n3][0].fixed.interface_name
        self.state.upf_conf.nfs.upf.n4.interface_name = self.state.vm_upf.network_interfaces[self.create_config.networks.n4][0].fixed.interface_name
        self.state.upf_conf.nfs.upf.n6.interface_name = self.state.vm_upf.network_interfaces[self.create_config.networks.n6][0].fixed.interface_name
        self.state.upf_conf.nfs.upf.n9.interface_name = self.state.vm_upf.network_interfaces[self.create_config.networks.n4][0].fixed.interface_name

        for new_slice in upf_config.slices:
            new_snssai: Snssai = oai_utils.add_snssai(self.state.upf_conf, new_slice.id, new_slice.type)
            for dnn in new_slice.dnnList:
                dnn_item = DnnItem(
                    dnn=dnn.name
                )
                # Add DNNS
                oai_utils.add_dnn_dnns(self.state.upf_conf, dnn.name, dnn.cidr)
                oai_utils.add_dnn_snssai_upf_info_list_item(self.state.upf_conf, new_snssai, dnn_item)

        upf_conf_yaml = yaml.dump(json.loads(self.state.upf_conf.model_dump_json(by_alias=True)))

        self.state.vm_upf_configurator.upf_id = self.state.area_id
        self.state.vm_upf_configurator.nrf_ipv4_address = upf_config.nrf_ip
        self.state.vm_upf_configurator.upf_conf = upf_conf_yaml

        self.provider.configure_vm(self.state.vm_upf_configurator)

    def get_ip(self):
        """

        Returns: IP of the vm

        """
        return self.state.vm_upf.network_interfaces[self.create_config.networks.n4][0].fixed.ip

