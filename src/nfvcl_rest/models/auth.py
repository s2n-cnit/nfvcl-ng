from enum import Enum
from typing import Optional

from fastapi import Form
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import Field

from nfvcl_core.models.base_model import NFVCLBaseModel


class OAuth2PasswordAndRefreshRequestForm(OAuth2PasswordRequestForm):
    """
    Modified from fastapi.security.OAuth2PasswordRequestForm to include refresh_token and scope fields.

    Based on discussion https://github.com/fastapi/fastapi/discussions/8879 and issue https://github.com/fastapi/fastapi/issues/3303
    """

    def __init__(
        self,
        grant_type: str = Form(default=None, regex="password|refresh_token"),
        username: str = Form(default=""),
        password: str = Form(default=""),
        refresh_token: str = Form(default=""),
        scope: str = Form(default=""),
        client_id: str | None = Form(default=None),
        client_secret: str | None = Form(default=None),
    ):
        super().__init__(
            grant_type=grant_type,
            username=username,
            password=password,
            client_id=client_id,
            client_secret=client_secret,
        )
        self.scopes = scope.split()
        self.refresh_token = refresh_token


class Oauth2Errors(str, Enum):
    """
    Enum representing the supported OAuth2 errors.
    """
    INVALID_REQUEST = 'invalid_request'
    INVALID_CLIENT = 'invalid_client'
    INVALID_GRANT = 'invalid_grant'
    UNAUTHORIZED_CLIENT = 'unauthorized_client'
    UNSUPPORTED_GRANT_TYPE = 'unsupported_grant_type'


class OAuth2Response(NFVCLBaseModel):
    """
    https://datatracker.ietf.org/doc/html/rfc6749#section-5.2
    """
    refresh_token: Optional[str] = Field(default=None)
    access_token: Optional[str] = Field(default=None)
    error: Optional[Oauth2Errors] = Field(default=None)
    error_description: Optional[str] = Field(default=None)
    error_uri: Optional[str] = Field(default=None)


class Oauth2CustomException(Exception):
    """
    Custom exception to be raised when an OAuth2 error occurs.
    """

    def __init__(self, status_code: int, error: Oauth2Errors, description: Optional[str] = None, uri: Optional[str] = None):
        self.status_code = status_code
        self.error = error
        self.description = description
        self.uri = uri
