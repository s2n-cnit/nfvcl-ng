import abc
from typing import Callable, Optional

from nfvcl_common.utils.log import create_logger
from nfvcl_core_models.providers.providers import BlueprintNGProviderData


class BlueprintNGProviderInterface(abc.ABC):
    area: int
    data: BlueprintNGProviderData

    def __init__(
        self,
        area: int,
        blueprint_id: str,
        persistence_function: Optional[Callable] = None
    ):
        super().__init__()
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
