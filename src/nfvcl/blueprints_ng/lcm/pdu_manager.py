from __future__ import annotations
from typing import Dict


__pdu_manager: PDUManager | None = None

def get_pdu_manager() -> PDUManager:
    """
    Allow to retrieve the BlueprintManager (that can have only one instance)
    Returns:
        The blueprint manager
    """
    global __pdu_manager
    if __pdu_manager is not None:
        return __pdu_manager
    else:
        __pdu_manager = PDUManager()
        return __pdu_manager

class PDUManagerException(Exception):
    pass

class PDUManager:
    registered_implementations: Dict[str, str]

    def __init__(self):
        super().__init__()
        self.registered_implementations = {}

    def register_implementation(self, name: str, implementation: str) -> None:
        self.registered_implementations[name] = implementation

    def get_implementation(self, name: str) -> str:
        if name not in self.registered_implementations:
            raise PDUManagerException(f"A PDU implementation with name '{name}' was not registered'")
        return self.registered_implementations[name]
