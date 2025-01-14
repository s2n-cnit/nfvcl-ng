from __future__ import annotations
from typing import Dict

from nfvcl_core.managers import GenericManager

class PDUManagerException(Exception):
    pass


class PDUManager(GenericManager):
    registered_implementations: Dict[str, str]

    def __init__(self):
        super().__init__()
        self.registered_implementations = {}

    def register_implementation(self, name: str, implementation: str) -> None:
        self.logger.debug(f"Registering PDU implementation '{name}'")
        self.registered_implementations[name] = implementation

    def get_implementation(self, name: str) -> str:
        if name not in self.registered_implementations:
            raise PDUManagerException(f"A PDU implementation with name '{name}' was not registered'")
        return self.registered_implementations[name]
