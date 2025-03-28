from __future__ import annotations

import hashlib
import random
import string
from datetime import datetime
from typing import Dict, List

from pydantic import ValidationError

from nfvcl_core.database.user_repository import UserRepository
from nfvcl_core_models.user import User, USER_PASSWORD_HASH_ALGORITHM
from nfvcl_core.managers import GenericManager
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.user import UserRole, UserCreateREST, UserNoConfidence, TokenStatus
from nfvcl_core.utils.auth.tokens import create_tokens_for_user, DB_TOKEN_HASH_ALGORITHM, decode_refresh_token, \
    decode_access_token


class UserManager(GenericManager):
    users: Dict[str, User]

    def __init__(self, user_repository: UserRepository):
        super().__init__()
        self._user_repository = user_repository
        self.users = {}

    def load(self):
        self._load_from_db()

    def _load_from_db(self):
        """
        Load all users from the database in the manager
        """
        for user_to_load in self._user_repository.get_all_dict():
            if user_to_load:
                try:
                    self.users[user_to_load['username']] = User.model_validate(user_to_load)
                    self.logger.debug(f"Loaded user {user_to_load['username']}")
                except ValidationError as e:
                    self.logger.warning(f"Unable to load user {user_to_load['username']}: {e}")
            else:
                self.logger.warning(f"Unable to load user {user_to_load['username']}")
        if len(self.users) == 0:
            self.logger.warning("No users found in the database, creating the admin user")
            self.add_user(User(username="admin", password_hash="admin", role=UserRole.ADMIN))

    def get_user_by_username(self, username: str) -> User:
        """
        Get a user by username.
        Args:
            username: The username of the user to be retrieved.

        Returns:
            The User with that username.

        Raises:
            NFVCLCoreException (404): If no user is found with that username.
        """
        if username in self.users:
            element = self.users[username]
            if element:
                return element
        raise NFVCLCoreException(f"No user found with username '{username}'", 404)
        # ValueError(f"No user found with username '{username}'"))

    def get_censored_user_by_username(self, username: str) -> UserNoConfidence:
        """
        Get a user by username without confidence data.
        Args:
            username: The username of the user to be retrieved.

        Returns:
            The UserNoConfidence with that username.

        Raises:
            NFVCLCoreException (404): If no user is found with that username.
        """
        return self.get_user_by_username(username).get_no_confidence_model()

    def get_users(self) -> List[User]:
        """
        Get all users loaded in the manager.
        Returns:
            List[User]: A list of all users.
        """
        return list(self.users.values())

    def get_censored_users(self) -> List[UserNoConfidence]:
        """
        Get all users loaded in the manager without confidence data.
        Returns:
            List[UserNoConfidence]: A list of all users without confidence data.
        """
        censored_list = [user.get_no_confidence_model() for user in list(self.users.values())]
        return censored_list

    def add_user(self, user: User) -> User:
        """
        Add a user to the manager and save it into the database.
        Args:
            user: The user to be added.

        Returns:
            User: The user added to the system.

        Raises:
            NFVCLCoreException (409): If a user with the same username already exists.
        """
        if user.username in self.users:
            raise NFVCLCoreException(f"User with username '{user.username}' already exists", 409)
        self.users[user.username] = user
        self._user_repository.save_user(user)
        return user

    def add_user_rest(self, user: UserCreateREST) -> UserNoConfidence:
        """
        Add a user to the manager and save it in the database, using the REST model.
        Args:
            user: The user to be added.

        Returns:
            UserNoConfidence: The user added to the system without confidence data.

        Raises:
            NFVCLCoreException (409): If a user with the same username already exists.
        """
        complete_user = User(username=user.username, password_hash=hashlib.sha256(user.password.encode()).hexdigest(), role=user.role, email=user.email)
        self.add_user(complete_user)
        return complete_user.get_no_confidence_model()

    def update_user(self, user: User) -> User:
        """
        Update a user in the manager and save it into the database.
        Args:
            user: The user to be updated.

        Returns:
            User: The user updated in the system.

        Raises:
            NFVCLCoreException (404): If no user is found with that username.
        """
        if user.username in self.users:
            user.id = self.users[user.username].id  # ID MUST BE PRESERVED
            self.users[user.username] = user
            self._user_repository.save_user(user)
            return user
        raise NFVCLCoreException(f"User with username '{user.username}' does NOT exists", 404)

    def delete_user(self, username: str) -> UserNoConfidence:
        """
        Delete a user from the manager and the database.
        Args:
            username: The username of the user to be deleted.

        Returns:
            UserNoConfidence: The user deleted from the system.

        Raises:
            NFVCLCoreException (404): If no user is found with that username.
            Exception: If the user to be deleted is the admin user.
        """
        if username == "admin":
            raise Exception("Cannot delete the admin user")
        if username in self.users:
            deleted_user = self.users[username]
            del self.users[username]
            self._user_repository.delete_user(username)
            return deleted_user.get_no_confidence_model()
        else:
            raise NFVCLCoreException(f"User with username '{username}' does NOT exists", 404)

    ############################### LOGIN ########################################

    def login(self, username: str, password: str) -> tuple[str, str]:
        """
        Login a user and generate access and refresh tokens.
        Args:
            username: The username of the user to be logged in.
            password: The password of the user to be logged in.

        Returns:
            access_token, refresh_token: The access and refresh tokens.

        Raises:
            NFVCLCoreException (404): If no user is found with that username.
            NFVCLCoreException (401): If the password is incorrect.
        """
        user = self.get_user_by_username(username)  # Raise 401 if user not found
        hash_function = getattr(hashlib, USER_PASSWORD_HASH_ALGORITHM)
        if user.password_hash == hash_function(password.encode()).hexdigest():
            access_token, refresh_token = create_tokens_for_user(user)
            self.update_user(user)
            self.logger.debug(f"User {user.username} logged in")
            return access_token, refresh_token
        raise NFVCLCoreException("Invalid username/password", 401)

    def logout(self, access_token: str) -> TokenStatus:
        """
        Logout a user by deleting the access and refresh tokens
        Args:
            access_token: The access token of the user.

        Returns:
            TokenStatus: The status of the token deletion.
        """
        token_status, user = self.check_token(access_token)
        if token_status == TokenStatus.VALID.value:
            user.access_token_hashed = None
            user.refresh_token_hashed = None
            user.access_token_expiration = None
            user.refresh_token_expiration = None
            self.update_user(user)
            self.logger.debug(f"User {user.username} logged out")
            return TokenStatus.DELETED
        else:
            return token_status

    def refresh_token(self, refresh_token: str) -> tuple[str, str]:
        """
        Refresh the access and refresh tokens.
        Args:
            refresh_token: The refresh token to be used to generate new tokens.

        Returns:
            access_token, refresh_token: The access and refresh tokens.

        Raises:
            NFVCLCoreException (401): If the refresh token is invalid.
        """
        decoded_token = decode_refresh_token(refresh_token)
        if decoded_token is not None:
            user = self.get_user_by_username(decoded_token.username)
            hash_function = getattr(hashlib, DB_TOKEN_HASH_ALGORITHM)
            if user.refresh_token_hashed == hash_function(refresh_token.encode()).hexdigest():
                access_token, refresh_token = create_tokens_for_user(user)
                self.update_user(user)
                self.logger.debug(f"User {user.username} has refreshed tokens")
                return access_token, refresh_token
        raise NFVCLCoreException("Invalid refresh token", 401)

    def check_token(self, access_token: str) -> tuple[TokenStatus, User | None]:
        """
        Check the validity of an access token.
        Args:
            access_token: The access token to be checked.

        Returns:
            TokenStatus: The status of the token.
            User: The user associated with the token.
        """
        decoded_token = decode_access_token(access_token)
        if decoded_token is not None:
            user = self.get_user_by_username(decoded_token.username)
            hash_function = getattr(hashlib, DB_TOKEN_HASH_ALGORITHM)
            hashed_token = hash_function(access_token.encode()).hexdigest()
            if user.access_token_hashed == hashed_token and user.access_token_hashed is not None:
                # The token is the same as in the DB but is it expired?
                if user.access_token_expiration > datetime.now(user.access_token_expiration.tzinfo):
                    return TokenStatus.VALID, user
                else:
                    self.logger.debug(f"Access token expired for user {user.username}")
                    return TokenStatus.EXPIRED, None
            else:
                self.logger.debug(f"Invalid access token for user {user.username}")
                return TokenStatus.INVALID, None
        self.logger.debug(f"Invalid access token received")
        return TokenStatus.INVALID, None

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
        self.update_user(user_b)  # Different object but the username is the key and it is equal to the previous
        one_user_list_b = self.get_users()
        assert len(one_user_list_b) == 1
        assert len(one_user_list_a) == 1
        assert one_user_list_b[0].password_hash == "1234"  # PASSWORD MUST BE UPDATED
        assert one_user_list_b[0].id == user_a.id  # ID MUST BE PRESERVED AFTER UPDATE
        assert user_b in one_user_list_b
        # DELETION, list a and b should not change
        self.delete_user(username)
        zero_user_list_c = self.get_users()
        assert len(one_user_list_b) == 1
        assert len(one_user_list_a) == 1
        assert len(zero_user_list_c) == 0
        # Checking admin cannot be deleted
        self.add_user(User(username="admin", password_hash="abcd"))
        self.delete_user("admin")
        list_only_admin = self.get_users()
        assert len(list_only_admin) == 1
