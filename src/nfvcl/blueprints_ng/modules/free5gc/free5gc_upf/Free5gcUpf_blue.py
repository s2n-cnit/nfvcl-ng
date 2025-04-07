import copy
import json
from typing import Optional

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf_vm import Generic5GUPFVMBlueprintNGState, Generic5GUPFVMBlueprintNG
from nfvcl_core.blueprints.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.free5gc import free5gc_default_upf_config
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import DeployedUPFInfo
from nfvcl_core_models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address
from nfvcl_core_models.resources import VmResourceImage, VmResourceFlavor, VmResource, VmResourceAnsibleConfiguration
from nfvcl_models.blueprint_ng.free5gc.free5gcUpf import Free5gcUpfConfig, DnnListItem, IfListItem
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo
from nfvcl_core.utils.blue_utils import rel_path, yaml

FREE5GC_UPF_BLUE_TYPE = "free5gc_upf"


class Free5gcUpfConfigurator(VmResourceAnsibleConfiguration):
    """
    This class is an example for an Ansible configurator for a VM

    The fields in this class will be saved to the DB and can be used to customize the configuration at runtime
    """
    upf_id: Optional[int] = Field(default=None)
    upf_conf: Optional[str] = Field(default=None)
    n6: Optional[str] = Field(default=None)
    n3_gateway: Optional[str] = Field(default=None)
    n6_gateway: Optional[str] = Field(default=None)
    gnb_cidr: Optional[str] = Field(default=None)

    def dump_playbook(self) -> str:
        """
        This method need to be implemented, it should return the Ansible playbook as a string
        """

        ansible_builder = AnsiblePlaybookBuilder("Playbook Free5gcUpfConfigurator")

        ansible_builder.add_template_task(rel_path("start.sh.jinja2"), "/root/Free5GC_UPF/start.sh")
        ansible_builder.add_template_task(rel_path("stop.sh.jinja2"), "/root/Free5GC_UPF/stop.sh")
        ansible_builder.add_template_task(rel_path("free5gc_upf.service.jinja2"), "/etc/systemd/system/free5gc_upf.service")

        ansible_builder.add_template_task(rel_path("compose.jinja2"), "/root/Free5GC_UPF/docker-compose.yaml")
        ansible_builder.add_template_task(rel_path("upf_conf.jinja2"), "/root/Free5GC_UPF/config/upfcfg.yaml")

        ansible_builder.add_template_task(rel_path("upf_forward.sh.jinja2"), "/opt/upf_forward.sh")
        ansible_builder.add_template_task(rel_path("upf_forward.service.jinja2"), "/etc/systemd/system/upf_forward.service")
        ansible_builder.add_shell_task("systemctl daemon-reload")

        ansible_builder.add_tasks_from_file(rel_path("compose.yaml"))

        ansible_builder.set_var("upf_id", self.upf_id)
        ansible_builder.set_var("upf_conf", self.upf_conf)
        ansible_builder.set_var("n6", self.n6)
        ansible_builder.set_var("n6_gateway", self.n6)
        ansible_builder.set_var("n3_gateway", self.n3_gateway)
        ansible_builder.set_var("gnb_cidr", self.gnb_cidr)

        ansible_builder.add_service_task("upf_forward", ServiceState.STARTED, True)
        ansible_builder.add_service_task("free5gc_upf", ServiceState.RESTARTED, True)

        # Build the playbook and return it
        return ansible_builder.build()


class Free5GCUpfBlueprintNGState(Generic5GUPFVMBlueprintNGState):
    """
    This class represent the current state of the blueprint, the data contained in this class will be saved to the DB

    Every Resource should be stored in a variable in this class to be able to access it after the initial creation

    Everything in this class should be serializable by Pydantic

    Every field need to be Optional because the state is created empty
    """
    upf_vm_configurator: Optional[Free5gcUpfConfigurator] = Field(default=None)
    upf_conf: Optional[Free5gcUpfConfig] = Field(default=None)


@blueprint_type(FREE5GC_UPF_BLUE_TYPE)
class Free5GCUpf(Generic5GUPFVMBlueprintNG[Free5GCUpfBlueprintNGState, UPFBlueCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFVMBlueprintNGState] = Free5GCUpfBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create_upf(self):
        self.logger.info("Starting creation of Free5gcUpf blueprint")
        self.state.upf_conf = copy.deepcopy(free5gc_default_upf_config.default_upf_config)

        upf_vm = VmResource(
            area=self.state.current_config.area_id,
            name=f"{self.id}_FREE5GC_UPF_{self.state.current_config.area_id}",
            image=VmResourceImage(name="Free5GC_UPF_4.0.0", url="https://images.tnt-lab.unige.it/free5gcupf/free5gcupf-v4.0.0-ubuntu2204.qcow2"),
            flavor=VmResourceFlavor(),
            username="ubuntu",
            password="ubuntu",
            management_network=self.state.current_config.networks.mgt.net_name,
            additional_networks=[self.state.current_config.networks.n4.net_name, self.state.current_config.networks.n3.net_name, self.state.current_config.networks.n6.net_name]
        )
        self.register_resource(upf_vm)
        self.provider.create_vm(upf_vm)
        self.state.vm_resources[upf_vm.id] = upf_vm

        self.state.upf_vm_configurator = Free5gcUpfConfigurator(vm_resource=upf_vm)
        self.register_resource(self.state.upf_vm_configurator)
        self.update_upf()

        self.update_upf_info()

    def update_upf(self):
        """
          Configure upf on first boot.
          :return: day2 instruction to configure upf at the first boot.

        Args:
            upf_config:
          """
        # Clearing previous config
        self.state.upf_conf.gtpu.if_list.clear()
        self.state.upf_conf.dnn_list.clear()

        vm_upf = next(iter(self.state.vm_resources.values()))

        self.state.upf_conf.pfcp.addr = vm_upf.network_interfaces[self.create_config.networks.n4.net_name][0].fixed.ip
        self.state.upf_conf.pfcp.node_id = vm_upf.network_interfaces[self.create_config.networks.n4.net_name][0].fixed.ip

        if_list_item = IfListItem(
            addr=vm_upf.network_interfaces[self.create_config.networks.n3.net_name][0].fixed.ip,
            type="N3"
        )
        self.state.upf_conf.gtpu.if_list.append(if_list_item)

        for new_slice in self.state.current_config.slices:
            for dnn in new_slice.dnn_list:
                dnn_item = DnnListItem(
                    dnn=dnn.dnn,
                    cidr=dnn.cidr
                )
                if dnn_item not in self.state.upf_conf.dnn_list:
                    self.state.upf_conf.dnn_list.append(dnn_item)

        upf_conf_yaml = yaml.dump(json.loads(self.state.upf_conf.model_dump_json(by_alias=True)))

        self.state.upf_vm_configurator.upf_id = self.state.current_config.area_id
        self.state.upf_vm_configurator.upf_conf = upf_conf_yaml
        self.state.upf_vm_configurator.n6 = vm_upf.network_interfaces[self.state.current_config.networks.n6.net_name][0].fixed.interface_name
        self.state.upf_vm_configurator.gnb_cidr = self.state.current_config.gnb_cidr.exploded
        self.state.upf_vm_configurator.n3_gateway = self.state.current_config.n3_gateway_ip.exploded
        self.state.upf_vm_configurator.n6_gateway = self.state.current_config.n6_gateway_ip.exploded

        self.provider.configure_vm(self.state.upf_vm_configurator)

    def update_upf_info(self):
        vm_upf = next(iter(self.state.vm_resources.values()))

        deployed_upf_info = DeployedUPFInfo(
            area=self.state.current_config.area_id,
            served_slices=self.state.current_config.slices,
            vm_resource_id=vm_upf.id,
            vm_configurator_id=self.state.upf_vm_configurator.id,
            network_info=UPFNetworkInfo(
                n4_cidr=SerializableIPv4Network(vm_upf.network_interfaces[self.state.current_config.networks.n4.net_name][0].fixed.cidr),
                n3_cidr=SerializableIPv4Network(vm_upf.network_interfaces[self.state.current_config.networks.n3.net_name][0].fixed.cidr),
                n6_cidr=SerializableIPv4Network(vm_upf.network_interfaces[self.state.current_config.networks.n6.net_name][0].fixed.cidr),
                n4_ip=SerializableIPv4Address(vm_upf.network_interfaces[self.state.current_config.networks.n4.net_name][0].fixed.ip),
                n3_ip=SerializableIPv4Address(vm_upf.network_interfaces[self.state.current_config.networks.n3.net_name][0].fixed.ip),
                n6_ip=SerializableIPv4Address(vm_upf.network_interfaces[self.state.current_config.networks.n6.net_name][0].fixed.ip)
            )
        )
        self.state.upf_list.clear()
        self.state.upf_list.append(deployed_upf_info)
