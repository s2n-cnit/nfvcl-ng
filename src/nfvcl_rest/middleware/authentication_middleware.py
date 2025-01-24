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
    if get_nfvcl_config().authentication:
        valid, user = user_manager.check_token(token)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user.username
    return "admin"


# example of user authentication
# class User(BaseModel):
#     username: str
#     password: str
#
#
# users_db = {
#     "user1": User(username="user1", password="password1"),
#     "user2": User(username="user2", password="password2"),
# }
#
# SECRET_KEY = "your-secret-key"
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 30
#
# from jose import JWTError, jwt
#

#
# def create_access_token(data: dict):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt
#
# def get_current_user(token: str = Depends(oauth2_scheme)):
#     credentials_exception = HTTPException(
#         status_code=401,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None:
#             raise credentials_exception
#         return username
#     except JWTError:
#         raise credentials_exception
#
#
# def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
#     user = users_db.get(form_data.username)
#     if user is None or user.password != form_data.password:
#         raise HTTPException(status_code=400, detail="Incorrect username or password")
#     access_token = create_access_token(data={"sub": user.username})
#     return {"access_token": access_token, "token_type": "bearer"}
#
#
