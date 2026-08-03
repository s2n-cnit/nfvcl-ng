from typing import List

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.providers.providers import ProviderData
from nfvcl_core_models.resources import VmResource


class RpcapdVmDeployment(NFVCLBaseModel):
    vm_resource: VmResource = Field()


class RpcapdVmStatus(NFVCLBaseModel):
    vm_name: str = Field()
    installed: bool = Field()
    running: bool = Field()
    service_state: str = Field()


class DiagnosticProviderData(ProviderData):
    rpcapd_vm_deployments: List[RpcapdVmDeployment] = Field(default_factory=list)


class DiagnosticProviderException(Exception):
    pass
