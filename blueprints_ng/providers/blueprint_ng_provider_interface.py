from __future__ import annotations

import abc

from topology.topology import build_topology

from models.base_model import NFVCLBaseModel
from utils.log import create_logger


class BlueprintNGProviderData(NFVCLBaseModel):
    pass


class BlueprintNGProviderException(Exception):
    pass


global_topology = build_topology()


class BlueprintNGProviderInterface(abc.ABC):
    area: int
    data: BlueprintNGProviderData

    def __init__(self, area, blueprint):
        super().__init__()
        self.area = area
        self.blueprint = blueprint
        self.logger = create_logger(self.__class__.__name__, blueprintid=self.blueprint.id)
        self.topology = global_topology
        self.init()

    @abc.abstractmethod
    def init(self):
        pass

    @abc.abstractmethod
    def final_cleanup(self):
        pass
