from nfvcl_core.database.database_repository import DatabaseRepository
from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_core_models.user import User


class UserRepository(DatabaseRepository[User]):
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, "users", data_type = User)

    def save_user(self, user: User):
        if self.collection.find_one({'username': user.username}):
            self.collection.update_one({'username': user.username}, {'$set': user.model_dump()})
        else:
            self.collection.insert_one(user.model_dump())

    def delete_user(self, username: str):
        assert username != "admin", "Cannot delete admin user"
        self.collection.delete_one({'username': username})
