from typing import List

from verboselogs import VerboseLogger

from nfvcl_common.utils.log import create_logger
from nfvcl_core_models.vim.vim_models import VimModel


class VimClient:
    def __init__(self, vim: VimModel):
        self.logger: VerboseLogger = create_logger(self.__class__.__name__)
        self.vim = vim
        self.references: List[int] = []
        self.closed = False

    def close(self):
        self.closed = True

    def __del__(self):
        self.close()
