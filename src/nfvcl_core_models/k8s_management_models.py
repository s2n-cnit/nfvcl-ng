from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel


class Labels(NFVCLBaseModel):
    labels: dict[str,str] = Field()
