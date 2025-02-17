import traceback

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from starlette import status
from starlette.responses import JSONResponse
from verboselogs import VerboseLogger

from nfvcl_core.config import NFVCLConfigModel, load_nfvcl_config
from nfvcl_core.managers.user_manager import UserManager
from nfvcl_core.models.user import TokenStatus
from nfvcl_core.utils.log import create_logger
from nfvcl_rest.models.auth import OAuth2PasswordAndRefreshRequestForm, OAuth2Response, Oauth2Errors, \
    Oauth2CustomException

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
user_manager: UserManager
nfvcl_config: NFVCLConfigModel
logger: VerboseLogger = create_logger("NFVCL_REST_AUTH")


def set_user_manager(manager: UserManager):
    """
    Set the global user manager instance.

    Args:
        manager (UserManager): The user manager instance to be set globally.
    """
    global user_manager
    user_manager = manager


def get_nfvcl_config(config: NFVCLConfigModel = Depends()) -> NFVCLConfigModel:
    global nfvcl_config
    if 'nfvcl_config' not in globals():
        nfvcl_config = None
    if not nfvcl_config:
        nfvcl_config = load_nfvcl_config()
    return nfvcl_config


def token(form_data: OAuth2PasswordAndRefreshRequestForm = Depends()):
    """
    Handle user login and return access and refresh tokens. Oauth2 standard requires the same endpoint to manage generation and refresh of tokens.

    Args:
        form_data (OAuth2PasswordAndRefreshRequestForm): The form data containing username and password and refresh token in case.

    Returns:
        dict: A dictionary containing the access and refresh tokens.

    Raises:
        HTTPException: If the login fails due to incorrect username or password.
    """
    try:
        match form_data.grant_type:
            case "password":
                access_token, refresh_token = user_manager.login(form_data.username, form_data.password)
            case "refresh_token":
                access_token, refresh_token = user_manager.refresh_token(form_data.refresh_token)
            case _:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid grant type", headers={"WWW-Authenticate": "Bearer"}, )
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return OAuth2Response(access_token=access_token, refresh_token=refresh_token)


def _handle_token_status(token_status: TokenStatus):
    """
    Handle the token status and return the appropriate response or raise the appropriate exception.
    Args:
        token_status: The status of the token.

    Returns:
        str: The response message.

    Raises:
        Oauth2CustomException: If the token is invalid or expired.
        HTTPException: If the token status is not recognized.
    """
    match token_status:
        case TokenStatus.VALID.value:
            return "OK"
        case TokenStatus.EXPIRED.value:
            # 400 -> https://datatracker.ietf.org/doc/html/rfc6749#section-5.2
            raise Oauth2CustomException(status_code=status.HTTP_400_BAD_REQUEST, error=Oauth2Errors.INVALID_GRANT, description="Token Expired")
        case TokenStatus.INVALID.value:
            # 400 -> https://datatracker.ietf.org/doc/html/rfc6749#section-5.2
            raise Oauth2CustomException(status_code=status.HTTP_400_BAD_REQUEST, error=Oauth2Errors.INVALID_GRANT, description="Invalid token")
        case TokenStatus.DELETED.value:
            return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=OAuth2Response().model_dump(exclude_none=True))
        case _:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="", headers={"WWW-Authenticate": "Bearer"}, )


def control_token(access_token: str = Depends(oauth2_scheme)):
    """
    Validate the provided token and return the username if valid.

    Args:
        access_token (str): The token to be validated.

    Returns:
        str: The username associated with the valid token.

    Raises:
        HTTPException: If the token is invalid.
    """
    if get_nfvcl_config().nfvcl.authentication:
        token_status, user = user_manager.check_token(access_token)
        return _handle_token_status(token_status)
    return "admin"


def logout(token: str = Depends(oauth2_scheme)):
    """
    Handle user logout.

    Args:
        token (str): The token to be invalidated.
    """
    token_status = user_manager.logout(token)
    return _handle_token_status(token_status)
