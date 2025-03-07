from typing import List

from nfvcl_core.utils.log import create_logger
from nfvcl_core_models.vim import VimModel


class VimClient:
    def __init__(self, vim: VimModel):
        self.logger = create_logger(self.__class__.__name__)
        self.vim = vim
        self.references: List[int] = []

    def close(self):
        pass

    def __del__(self):
        self.close()
