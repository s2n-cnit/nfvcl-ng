from typing import Optional

from pydantic import Field

from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import Generic5GUPFBlueprintNG, Generic5GUPFBlueprintNGState, DeployedUPFInfo
from nfvcl.blueprints_ng.pdu_configurators.implementations.core_5g.athonet.athonet_upf_pdu_configurator import AthonetUPFPDUConfigurator
from nfvcl.models.blueprint_ng.Athonet.upf import AthonetApplicationUpfConfig
from nfvcl.models.blueprint_ng.g5.upf import UPFBlueCreateModel, UPFNetworkInfo
from nfvcl_core.models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address
from nfvcl_core.models.network.network_models import PduType

ATHONET_UPF_BLUE_TYPE = "athonet_upf"


class AthonetUPFBlueprintNGState(Generic5GUPFBlueprintNGState):
    """
    This class represent the current state of the blueprint, the data contained in this class will be saved to the DB.

    Every Resource should be stored in a variable in this class to be able to access it after the initial creation.

    Everything in this class should be serializable by Pydantic.

    Every field need to be Optional because the state is created empty.

    """
    backup_config: Optional[AthonetApplicationUpfConfig] = Field(default=None)


@blueprint_type(ATHONET_UPF_BLUE_TYPE)
class AthonetUPF(Generic5GUPFBlueprintNG[AthonetUPFBlueprintNGState, UPFBlueCreateModel]):

    def __init__(self, blueprint_id: str, state_type: type[Generic5GUPFBlueprintNGState] = AthonetUPFBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB.

        """
        super().__init__(blueprint_id, state_type)

    def create_upf(self):
        pdu = self.provider.find_pdu(self.state.current_config.area_id, PduType.CORE5G, 'AthonetUPF')
        self.provider.lock_pdu(pdu)
        configurator: AthonetUPFPDUConfigurator = self.provider.get_pdu_configurator(pdu)
        self.state.backup_config = configurator.get_upf_application_config()
        configurator.configure(self.state.current_config)
        self.update_upf_info()

    def update_upf(self):
        pdu = self.provider.find_pdu(self.state.current_config.area_id, PduType.CORE5G, 'AthonetUPF')
        configurator: AthonetUPFPDUConfigurator = self.provider.get_pdu_configurator(pdu)
        configurator.configure(self.state.current_config)

    def update_upf_info(self):
        pdu = self.provider.find_pdu(self.state.current_config.area_id, PduType.CORE5G, 'AthonetUPF')
        configurator: AthonetUPFPDUConfigurator = self.provider.get_pdu_configurator(pdu)
        n3_ip, n3_cidr, n4_ip, n4_cidr = configurator.get_n_interfaces_ip()
        deployed_upf_info = DeployedUPFInfo(
            area=self.state.current_config.area_id,
            served_slices=self.state.current_config.slices,
            network_info=UPFNetworkInfo(
                n4_cidr=SerializableIPv4Network(n4_cidr),
                n3_cidr=SerializableIPv4Network(n3_cidr),
                n6_cidr=SerializableIPv4Network("128.0.0.0/24"),
                n4_ip=SerializableIPv4Address(n4_ip),
                n3_ip=SerializableIPv4Address(n3_ip),
                n6_ip=SerializableIPv4Address("128.0.0.1")
            )
        )
        self.state.upf_list.clear()
        self.state.upf_list.append(deployed_upf_info)

    def destroy(self):
        pdu = self.provider.find_pdu(self.state.current_config.area_id, PduType.CORE5G, 'AthonetUPF')
        configurator: AthonetUPFPDUConfigurator = self.provider.get_pdu_configurator(pdu)
        configurator.restore_base_config(self.state.backup_config)
        super().destroy()

