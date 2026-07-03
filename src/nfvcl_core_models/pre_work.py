from typing import Optional, Callable

from nfvcl_core_models.response_model import AsyncTaskResponse

from nfvcl_common.base_model import NFVCLBaseModel


class PreWorkCallbackResponse(NFVCLBaseModel):
    async_return: AsyncTaskResponse

def run_pre_work_callback(pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]], async_return: AsyncTaskResponse):
    if pre_work_callback:
        pre_work_callback(PreWorkCallbackResponse(async_return=async_return))
