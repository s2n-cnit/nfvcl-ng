import traceback

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from starlette import status
from verboselogs import VerboseLogger

from nfvcl_core.config import NFVCLConfigModel, load_nfvcl_config
from nfvcl_core.managers.user_manager import UserManager
from nfvcl_core.utils.log import create_logger

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

def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Handle user login and return access and refresh tokens.

    Args:
        form_data (OAuth2PasswordRequestForm): The form data containing username and password.

    Returns:
        dict: A dictionary containing the access and refresh tokens.

    Raises:
        HTTPException: If the login fails due to incorrect username or password.
    """
    try:
        access_token, refresh_token = user_manager.login(form_data.username, form_data.password)
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": access_token, "refresh_token": refresh_token}

def control_token(token: str = Depends(oauth2_scheme)):
    """
    Validate the provided token and return the username if valid.

    Args:
        token (str): The token to be validated.

    Returns:
        str: The username associated with the valid token.

    Raises:
        HTTPException: If the token is invalid.
    """
    if get_nfvcl_config().nfvcl.authentication:
        valid, user = user_manager.check_token(token)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user.username
    return "admin"

def logout(token: str = Depends(oauth2_scheme)):
    """
    Handle user logout.

    Args:
        token (str): The token to be invalidated.
    """
    user_manager.logout(token)
    return {"message": "Successfully logged out"}

