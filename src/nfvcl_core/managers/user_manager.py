from __future__ import annotations

import random
import string
from typing import Dict, List

from pydantic import ValidationError

from nfvcl_core.managers import GenericManager
from nfvcl_core.database.user_repository import UserRepository, User
from nfvcl_core.models.user import UserRole


class UserManager(GenericManager):
    users: Dict[str, User]

    def __init__(self, user_repository: UserRepository):
        super().__init__()
        self._user_repository = user_repository
        self.users = {}

    def load(self):
        self._load_from_db()

    def _load_from_db(self):
        for user_to_load in self._user_repository.get_all_dict():
            if user_to_load:
                try:
                    self.users[user_to_load['username']] = User.model_validate(user_to_load)
                    self.logger.debug(f"Loaded user {user_to_load['username']}")
                except ValidationError as e:
                    self.logger.warning(f"Unable to load user {user_to_load['username']}: {e}")
            else:
                self.logger.warning(f"Unable to load user {user_to_load['username']}")
        if len(self.users)==0:
            self.logger.warning("No users found in the database, creating the admin user")
            self.add_user(User(username="admin", password_hash="admin", role=UserRole.ADMIN))


    def get_user_by_username(self, username: str) -> User:
        element = self.users[username]
        if element:
            return element
        raise Exception(f"No user found with username '{username}'")

    def get_users(self) -> List[User]:
        return list(self.users.values())

    def add_user(self, user: User):
        if user.username in self.users:
            raise Exception(f"User with username '{user.username}' already exists")
        self.users[user.username] = user
        self._user_repository.save_user(user)

    def update_user(self, user: User):
        if user.username in self.users:
            user.id = self.users[user.username].id # ID MUST BE PRESERVED
            self.users[user.username] = user
            self._user_repository.save_user(user)
            return
        raise Exception(f"User with username '{user.username}' already exists")

    def delete_user(self, username: str):
        if username in self.users:
            del self.users[username]
            self._user_repository.delete_user(username)
        else:
            raise Exception(f"No user found with id '{username}'")

    def _test(self):
        username = 'XYZ'.join(random.choices(string.ascii_letters, k=4))
        user_a = User(username=username, password_hash="abcd")
        # ADDING a user to the DB
        self.add_user(user_a)
        one_user_list_a = self.get_users()
        assert user_a in one_user_list_a
        # UPDATING a user using the username key but with a different object
        user_b = User(username=username, password_hash="1234")
        self.update_user(user_b) # Different object but the username is the key and it is equal to the previous
        one_user_list_b = self.get_users()
        assert len(one_user_list_b) == 1
        assert len(one_user_list_a) == 1
        assert one_user_list_b[0].password_hash == "1234" # PASSWORD MUST BE UPDATED
        assert one_user_list_b[0].id == user_a.id # ID MUST BE PRESERVED AFTER UPDATE
        assert user_b in one_user_list_b
        # DELETION, list a and b should not change
        self.delete_user(username)
        zero_user_list_c = self.get_users()
        assert len(one_user_list_b) == 1
        assert len(one_user_list_a) == 1
        assert len(zero_user_list_c) == 0


