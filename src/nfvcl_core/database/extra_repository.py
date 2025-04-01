from nfvcl_core.utils.log import create_logger

from nfvcl_core.database.database_repository import DatabaseRepository
from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_core_models.user import User

# !!! DOES NOT EXTEND DATABASE REPOSITORY !!!

class ExtraRepository:
    def __init__(self, persistence_manager: PersistenceManager):
        self.logger = create_logger(self.__class__.__name__)
        self.logger.debug(f"{self.__class__.__name__} created")
        self.collection = persistence_manager.get_collection("extra")

    def save(self, id: str, data: dict):
        if self.find_one(id):
            return self.collection.update_one({'id': id}, {'$set': data})
        else:
            data['id'] = id
            return self.collection.insert_one(data)

    def find_one(self, id: str):
        found_obj = self.collection.find_one({'id': id}, projection={'_id': False})
        if found_obj:
            del found_obj['id']
        return found_obj

    def delete(self, id: str):
        if self.find_one(id):
            return self.collection.delete_one({'id': id})
        else:
            self.logger.warning(f"Trying to delete id {id} but it does not exist")
