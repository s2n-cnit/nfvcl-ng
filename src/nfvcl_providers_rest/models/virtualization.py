from typing import List

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel


class VmResourceAnsibleConfigurationSerialized(NFVCLBaseModel):
    ansible_playbook: str = Field()

class AttachNetPayload(NFVCLBaseModel):
    net_names: List[str] = Field()

class NetworkCheckPayload(NFVCLBaseModel):
    net_names: List[str] = Field()

class NetworkCheckResponse(NFVCLBaseModel):
    ok: bool = Field()
    missing_nets: List[str] = Field()
