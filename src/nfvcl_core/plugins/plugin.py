from abc import abstractmethod

from nfvcl_core import NFVCL


class NFVCLPlugin:
    def __init__(self, nfvcl_context: NFVCL, name: str):
        super().__init__()
        self.nfvcl_context = nfvcl_context
        self.name = name

    @abstractmethod
    def load(self):
        pass
