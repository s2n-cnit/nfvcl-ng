from typing import List

from verboselogs import VerboseLogger

from nfvcl_common.utils.log import create_logger
from nfvcl_core_models.vim.vim_models import VimModel


class VimClient:
    """
    Represents a VimClient class that provides methods for interacting with a VimModel.
    This class is extended for each specific VimClient implementation.
    This class is used to manage in a generalized fashion a VIM Client such that no specific code is required to be written for managing each VIM Client.

    Attributes:
        logger (VerboseLogger): The logger instance for logging messages.
        vim (VimModel): The VimModel instance associated with the VimClient.
        closed (bool): A flag indicating whether the VimClient is closed.
    """
    def __init__(self, vim: VimModel):
        self.logger: VerboseLogger = create_logger(self.__class__.__name__)
        self.vim = vim
        self.closed = False

    def close(self):
        self.closed = True

    def __del__(self):
        self.close()
