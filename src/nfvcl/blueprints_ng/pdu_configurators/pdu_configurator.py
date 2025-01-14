import abc

from nfvcl_core.models.network import PduModel

class PDUException(Exception):
    pass

class PDUConfigurator(abc.ABC):
    def __init__(self, pdu_model: PduModel):
        super().__init__()
        self.pdu_model = pdu_model

    @classmethod
    def get_class_path(cls) -> str:
        return cls.__module__ + "." + cls.__qualname__
