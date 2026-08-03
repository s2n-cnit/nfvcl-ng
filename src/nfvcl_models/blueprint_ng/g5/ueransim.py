from typing import List

from pydantic import Field

from nfvcl_models.blueprint_ng.g5.ue import UESim
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_models.blueprint_ng.blueprint_ueransim_model import UeransimArea, UeransimConfig, UeransimUe
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel


class UeransimBlueprintRequestInstance(BlueprintNGCreateModel):
    config: UeransimConfig
    areas: List[UeransimArea] = Field(
        ...,
        description='list of areas to instantiate the Blueprint',
        min_length=1
    )


class UeransimBlueprintRequestAddDelGNB(NFVCLBaseModel):
    area_id: str = Field()


class UeransimBlueprintRequestAddUE(NFVCLBaseModel):
    area_id: str = Field()
    ue: UeransimUe = Field()


class UeransimBlueprintRequestDelUE(NFVCLBaseModel):
    area_id: str = Field()
    ue_id: int = Field()


class UeransimBlueprintRequestAddSim(NFVCLBaseModel):
    area_id: str = Field()
    ue_id: int = Field()
    sim: UESim = Field()

class UeransimBlueprintRequestDelSim(NFVCLBaseModel):
    area_id: str = Field()
    ue_id: int = Field()
    imsi: str = Field()


class UeransimBlueprintRequestAddDelUe(NFVCLBaseModel):
    areas: List[UeransimArea] = Field(
        ...,
        description='List of areas with devices to be added',
        min_length=1
    )
