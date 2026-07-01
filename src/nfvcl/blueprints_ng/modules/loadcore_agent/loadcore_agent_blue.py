import copy
from typing import Optional, List, Dict

from pydantic import Field

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel, BlueprintNGState
from nfvcl_core_models.resources import VmResource, VmResourceImage, VmResourceFlavor, VmResourceAnsibleConfiguration, VmResourceNetworkInterface


class LoadCoreAgentCreateModel(BlueprintNGCreateModel):
    area_id: int = Field()
    mgmt_net: str = Field()
    additional_networks: Optional[List[str]] = Field(default_factory=list)
    middleware_ip: str = Field()

class LoadCoreAgentBlueprintNGState(BlueprintNGState):
    vm_loadcore_agent: Optional[VmResource] = Field(default=None)
    vm_loadcore_agent_configurator: Optional[LoadCoreAgentVmConfigurator] = Field(default=None)

class DeployedAgentInfo(NFVCLBaseModel):
    mgmt_ip: str = Field()
    network_interfaces: Dict[str, List[VmResourceNetworkInterface]] = Field()

class LoadCoreAgentVmConfigurator(VmResourceAnsibleConfiguration):
    mgmt_interface: str = Field(default="")
    middleware_ip: str = Field(default="")

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook LoadCoreAgentVmConfigurator")
        ansible_builder.add_shell_task(f"/home/ixia/agent-setup.sh {self.middleware_ip} {self.mgmt_interface} auto y '' n")
        return ansible_builder.build()

@blueprint_type("loadcore_agent")
class LoadCoreAgentBlueprintNG(BlueprintNG[LoadCoreAgentBlueprintNGState, LoadCoreAgentCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = LoadCoreAgentBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: LoadCoreAgentCreateModel):
        """
        This docstring for the create function will be shown on Swagger
        """
        super().create(create_model)
        self.logger.info("Starting creation of LoadCore Agent blueprint")

        # ################################# VMs Example #####################################

        # To describe a new VM create a VmResource object and save it in the state
        self.state.vm_loadcore_agent = VmResource(
            area=create_model.area_id,
            name=f"{self.id}_LoadCore_Agent_{self.create_config.area_id}",
            image=VmResourceImage(name="LoadCore-Agent-5.0.0.5", url="https://images.tnt-lab.unige.it/private/LoadCore/LoadCore-Agent-5.0.0.5-46d96cc313-20241217T163926Z.qcow2"),
            flavor=VmResourceFlavor(),
            username="ixia",
            password="ixia",
            become_password="ixia",
            management_network=create_model.mgmt_net,
            additional_networks=create_model.additional_networks,
            resource_group=self.id
        )
        self.register_resource(self.state.vm_loadcore_agent)
        self.provider.create_vm(self.state.vm_loadcore_agent)

        self.state.vm_loadcore_agent_configurator = LoadCoreAgentVmConfigurator(
            vm_resource=self.state.vm_loadcore_agent,
            mgmt_interface=self.state.vm_loadcore_agent.network_interfaces[self.state.vm_loadcore_agent.management_network][0].fixed.interface_name,
            middleware_ip=self.create_config.middleware_ip,
            resource_group=self.id
        )
        self.register_resource(self.state.vm_loadcore_agent_configurator)
        self.provider.configure_vm(self.state.vm_loadcore_agent_configurator)

    def get_agent_info(self) -> DeployedAgentInfo:
        return DeployedAgentInfo(
            mgmt_ip=self.state.vm_loadcore_agent.access_ip,
            network_interfaces=copy.deepcopy(self.state.vm_loadcore_agent.network_interfaces)
        )
