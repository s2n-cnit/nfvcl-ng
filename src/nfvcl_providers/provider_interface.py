import abc
from typing import Callable, Optional

from nfvcl_common.utils.log import create_logger
from nfvcl_core_models.providers.providers import ProviderData


class ProviderInterface(abc.ABC):
    data: ProviderData

    def __init__(
        self,
        persistence_function: Optional[Callable] = None
    ):
        super().__init__()
        self.save_to_db = persistence_function or (lambda: None)
        self.logger = create_logger(self.__class__.__name__)
        self.logger.debug(f"Creating {self.__class__.__name__}")
        self.init()

    @abc.abstractmethod
    def init(self):
        pass

    @abc.abstractmethod
    def cleanup_resource_group(self, resource_group: str):
        pass
