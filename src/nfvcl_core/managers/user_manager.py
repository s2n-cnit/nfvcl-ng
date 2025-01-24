from __future__ import annotations

import hashlib
import random
import string
from datetime import datetime, timezone
from typing import Dict, List

from pydantic import ValidationError

from nfvcl_core.managers import GenericManager
from nfvcl_core.database.user_repository import UserRepository, User
from nfvcl_core.models.user import UserRole
from nfvcl_core.utils.auth.tokens import decode_token, create_tokens_for_user, DB_TOKEN_HASH_ALGORITHM


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

    ############################### LOGIN ########################################

    def login(self, username: str, password: str) -> tuple[str, str]:
        """
        Returns:
        tuple[str, str]: The access and refresh tokens.
        """
        user = self.get_user_by_username(username)
        if user.password_hash == hashlib.sha256(password.encode()).hexdigest():
            access_token, refresh_token = create_tokens_for_user(user)
            self.update_user(user)
            return access_token, refresh_token
        raise Exception("Invalid username/password")

    def logout(self, access_token: str):
        valid, user = self.check_token(access_token)
        if valid:
            user.access_token_hashed = None
            user.refresh_token_hashed = None
            user.access_token_expiration = None
            user.refresh_token_expiration = None
        self.update_user(user)

    def renew_token(self, refresh_token: str) -> tuple[str, str]:
        decoded_token = decode_token(refresh_token)
        if decoded_token is not None:
            user = self.get_user_by_username(decoded_token.username)
            if user.refresh_token_hashed == getattr(hashlib, DB_TOKEN_HASH_ALGORITHM)(refresh_token.encode()).hexdigest():
                access_token, refresh_token = create_tokens_for_user(user)
                self.update_user(user)
                return access_token, refresh_token
        raise Exception("Invalid refresh token")

    def check_token(self, access_token: str) -> tuple[bool, User|None]:
        decoded_token = decode_token(access_token)
        if decoded_token is not None:
            user = self.get_user_by_username(decoded_token.username)
            hash_function = getattr(hashlib, DB_TOKEN_HASH_ALGORITHM)
            hashed_token = hash_function(access_token.encode()).hexdigest()
            if user.access_token_hashed == hashed_token and user.access_token_hashed is not None:
                # TODO we are setting the timezone to the one of the saved token, is this correct?
                # The token is the same as in the DB but is it expired?
                if user.access_token_expiration > datetime.now(user.access_token_expiration.tzinfo):
                    return True, user
                else:
                    self.logger.debug(f"Access token expired for user {user.username}")
                    return False, None
            else:
                self.logger.debug(f"Invalid access token for user {user.username}")
                return False, None
        self.logger.debug(f"Invalid access token received")
        return False, None

    ############################### TESTS ########################################

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


