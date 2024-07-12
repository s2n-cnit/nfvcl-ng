from __future__ import annotations

import abc
from typing import Callable, Optional

from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.topology.topology import build_topology
from nfvcl.utils.log import create_logger


class BlueprintNGProviderData(NFVCLBaseModel):
    pass


class BlueprintNGProviderException(Exception):
    pass


class BlueprintNGProviderInterface(abc.ABC):
    area: int
    data: BlueprintNGProviderData

    def __init__(self, area: int, blueprint_id: str, persistence_function: Optional[Callable] = None):
        super().__init__()
        self.area = area
        self.blueprint_id = blueprint_id
        self.save_to_db = persistence_function
        self.logger = create_logger(self.__class__.__name__, blueprintid=self.blueprint_id)
        self.topology = build_topology()
        self.logger.debug(f"Creating {self.__class__.__name__} for area {self.area}")
        self.init()

    @abc.abstractmethod
    def init(self):
        pass

    @abc.abstractmethod
    def final_cleanup(self):
        pass
