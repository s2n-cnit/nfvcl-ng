from typing import Any, Dict, Optional

from pydantic import Field, field_validator

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl_core_models.blueprints.blueprint import BlueprintNGState
from nfvcl_core_models.network.network_models import PduType, PduLockType
from nfvcl_core_models.pdu.ue import UEPDUConfigure
from nfvcl_core_models.resources import LXCContainerResource, LXCImage, ContainerResourceFlavor
from nfvcl_models.blueprint_ng.g5.custom_types_5g import DNNType, PLMNType

ATPY_UE_BLUE_TYPE = "atpy_ue"


class AtpyUeCreateModel(NFVCLBaseModel):
    area: int = Field()
    mgmt: Optional[str] = Field(default="incusbr0")
    dnn: Optional[DNNType] = Field(default=None, examples=["internet"])
    plmn: Optional[PLMNType] = Field(default=None, examples=["00101"])

class ExperimentEnv(NFVCLBaseModel):
    image_name: str = Field()
    tcpdump: bool = Field(default=False)
    docker_vars: Dict[str, str] = Field(default_factory=dict)

    @field_validator("docker_vars", mode="before")
    @classmethod
    def coerce_docker_vars_values(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): str(item) for key, item in value.items()}
        return value

class ExperimentNetInterface(NFVCLBaseModel):
    # iface_mac: str = Field()
    container_iface: str = Field()
    # modem_ip: str = Field()


class AtpyUeBlueprintNGState(BlueprintNGState):
    """

    """
    area: Optional[int] = Field(default=None)
    dnn: Optional[DNNType] = Field(default=None)
    plmn: Optional[PLMNType] = Field(default=None)
    experiment_net_interface: Optional[ExperimentNetInterface] = Field(default=None)


@blueprint_type(ATPY_UE_BLUE_TYPE)
class AtpyUeBlueprint(BlueprintNG[AtpyUeBlueprintNGState, AtpyUeCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = AtpyUeBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: AtpyUeCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of atpy_ue blueprint")
        self.state.dnn = create_model.dnn
        self.state.area = create_model.area
        self.state.plmn = create_model.plmn

        pdu = self.provider.find_pdu(self.state.area, PduType.UE, 'ATPY_UE')
        self.provider.lock_pdu(pdu, PduLockType.GENERIC)
        configurator = self.provider.get_pdu_configurator(pdu, PduLockType.GENERIC)

        iface = configurator.configure(UEPDUConfigure(dnn=self.state.dnn, plmn=self.state.plmn))

        container = LXCContainerResource(
            area=create_model.area,
            name=f"{self.id}",
            image=LXCImage(
                name="ubuntu24-docker-arm",
                url="https://images.tnt-lab.unige.it/private/Rasp/ubuntu24-docker-arm64.tar.gz"
            ),
            username="ubuntu",
            password="ubuntu",
            management_network=create_model.mgmt,
            additional_networks=[iface],
            resource_group=self.id,
            flavor=ContainerResourceFlavor(
                cpu_count=8,
                memory_mb=8192,
                storage_gb=10
            ),
            docker=True,
            privileged=True
        )
        self.register_resource(container)
        self.provider.create_container(container)

        container_iface = self.provider.get_container_interface_name_from_parent(container, iface)
        if container_iface:
            self.state.experiment_net_interface = ExperimentNetInterface(container_iface=container_iface)
        else:
            raise Exception("Failed to get container interface name from parent")

    def destroy(self):
        pdu = self.provider.find_pdu(self.state.area, PduType.UE, 'ATPY_UE')
        configurator = self.provider.get_pdu_configurator(pdu, PduLockType.GENERIC)
        configurator.cleanup()
        super().destroy()

    @day2_function("/run_experiment", [HttpRequestType.POST])
    def run_experiment(self, vars: ExperimentEnv):
        pdu = self.provider.find_pdu(self.state.area, PduType.UE, 'ATPY_UE')
        configurator = self.provider.get_pdu_configurator(pdu, PduLockType.GENERIC)
        env_vars = dict(vars.docker_vars)
        env_vars["INTERFACE"] = self.state.experiment_net_interface.container_iface
        configurator.run_experiment(
            container_name=self.id.lower(),
            container_image_name=vars.image_name,
            tcpdump=vars.tcpdump,
            container_iface=self.state.experiment_net_interface.container_iface,
            modem_ip="",
            iface_mac="",
            # modem_ip=self.state.experiment_net_interface.modem_ip,
            # iface_mac=self.state.experiment_net_interface.iface_mac,
            env_vars=env_vars
        )

