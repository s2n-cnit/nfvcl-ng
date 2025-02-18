from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_ran import Generic5GRANBlueprintNGState, Generic5GRANBlueprintNG
# from nfvcl.blueprints_ng.modules.oai.oai_ran.OpenAirInterfaceCUCP_blue import OAI_CUCP_BLUE_TYPE
from nfvcl.blueprints_ng.modules.oai.oai_ran.OpenAirInterfaceGNB_blue import OAI_GNB_BLUE_TYPE
from nfvcl_models.blueprint_ng.g5.ran import RANBlueCreateModel
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type

OAI_RAN_BLUE_TYPE = "oai_ran"


class OAIRanBlueprintNGState(Generic5GRANBlueprintNGState):
    pass


@blueprint_type(OAI_RAN_BLUE_TYPE)
class OpenAirInterfaceRan(Generic5GRANBlueprintNG[OAIRanBlueprintNGState, RANBlueCreateModel]):
    gnb_blue_type = OAI_GNB_BLUE_TYPE
    # cu_blue_type = OAI_CU_BLUE_TYPE
    cucp_blue_type = None
    # cuup_blue_type = OAI_CUUP_BLUE_TYPE
    # du_blue_type = OAI_DU_BLUE_TYPE
    implementation_name = "OAI"
    def __init__(self, blueprint_id: str, state_type: type[Generic5GRANBlueprintNGState] = OAIRanBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_ran(self):
        pass

    def update_ran(self):
        pass


