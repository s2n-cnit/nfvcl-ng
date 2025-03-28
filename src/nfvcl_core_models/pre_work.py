from typing import Optional, Callable

from nfvcl_core_models.response_model import OssCompliantResponse

from nfvcl_core_models.base_model import NFVCLBaseModel


class PreWorkCallbackResponse(NFVCLBaseModel):
    async_return: OssCompliantResponse

def run_pre_work_callback(pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]], async_return: OssCompliantResponse):
    if pre_work_callback:
        pre_work_callback(PreWorkCallbackResponse(async_return=async_return))
