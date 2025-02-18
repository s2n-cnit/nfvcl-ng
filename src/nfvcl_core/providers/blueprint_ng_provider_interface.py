from __future__ import annotations

import abc
from typing import Callable, Optional, TYPE_CHECKING

from nfvcl_core_models.providers.providers import BlueprintNGProviderData
from nfvcl_core.utils.log import create_logger
if TYPE_CHECKING:
    from nfvcl_core.managers import BlueprintManager, TopologyManager, PDUManager


class BlueprintNGProviderInterface(abc.ABC):
    area: int
    data: BlueprintNGProviderData

    def __init__(self, area: int, blueprint_id: str, topology_manager: TopologyManager = None, blueprint_manager: BlueprintManager = None, pdu_manager: PDUManager = None, persistence_function: Optional[Callable] = None):
        super().__init__()
        self.topology_manager = topology_manager
        self.blueprint_manager = blueprint_manager
        self.pdu_manager = pdu_manager
        self.topology = topology_manager.get_topology()
        self.area = area
        self.blueprint_id = blueprint_id
        self.save_to_db = persistence_function
        self.logger = create_logger(self.__class__.__name__, blueprintid=self.blueprint_id)
        self.logger.debug(f"Creating {self.__class__.__name__} for area {self.area}")
        self.init()

    def set_blueprint_id(self, blueprint_id: str):
        self.blueprint_id = blueprint_id

    @abc.abstractmethod
    def init(self):
        pass

    @abc.abstractmethod
    def final_cleanup(self):
        pass
