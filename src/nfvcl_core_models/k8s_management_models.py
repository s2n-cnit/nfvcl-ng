from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel


class Labels(NFVCLBaseModel):
    labels: dict[str,str] = Field()
