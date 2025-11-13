from typing import TypeVar, List

from pydantic import BaseModel
from typing_extensions import Generic

from nfvcl_common.utils.log import create_logger
from nfvcl_core.managers.persistence_manager import PersistenceManager

T = TypeVar('T', bound=BaseModel)

class DatabaseRepository(Generic[T]):
    def __init__(self, persistence_manager: PersistenceManager, collection_name: str, data_type: type[BaseModel]):
        self.logger = create_logger(self.__class__.__name__)
        self.logger.debug(f"{self.__class__.__name__} created")
        self.data_type = data_type
        self.collection = persistence_manager.get_collection(collection_name)

    def find_one(self, query: dict) -> T:
        return self.data_type.model_validate(self.collection.find_one(query, projection={'_id': False}))

    def find_one_safe(self, query: dict) -> T | None:
        result = self.collection.find_one(query, projection={'_id': False})
        if result is None:
            return None
        return self.data_type.model_validate(self.collection.find_one(query, projection={'_id': False}))

    # def update_one(self, query: dict, data: dict):
    #     return self.collection.update_one(query, {'$set': data})

    def get_all(self) -> List[T]:
        return [self.data_type.model_validate(element) for element in self.collection.find(projection={'_id': False})]

    def get_all_dict(self) -> List[dict]:
        return [element for element in self.collection.find(projection={'_id': False})]

    def save(self, data: T):
        if not isinstance(data, self.data_type):
            raise ValueError(f"Trying to save a '{type(data).__name__}' type but this repository is for '{self.data_type.__name__}'")
        return self.collection.insert_one(data.model_dump())

    def delete(self, data: T):
        if not isinstance(data, self.data_type):
            raise ValueError(f"Trying to save a '{type(data).__name__}' type but this repository is for '{self.data_type.__name__}'")
        return self.collection.delete_one(data.model_dump())

    def delete_all(self):
        return self.collection.delete_many({})
