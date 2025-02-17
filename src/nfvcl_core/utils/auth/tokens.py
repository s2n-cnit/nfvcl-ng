import hashlib
from datetime import datetime, timezone, timedelta

from jose import jwt, JWTError, ExpiredSignatureError

from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.user import User
from nfvcl_core.utils.util import generate_id

ACCESS_TOKEN_EXPIRE_MINUTES = 480
REFRESH_TOKEN_EXPIRE_DAYS = 7
USER_TOKEN_HASH_ALGORITHM = 'HS256'
DB_TOKEN_HASH_ALGORITHM = 'sha256'
SECRET_KEY_CHAR_SET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@!$%^&*()_+-=[]{}|;:,.<>?/"
# When NFVCL is restarted the secret keys are regenerated, this invalidates all the tokens but it should be fine.
SECRET_KEY = generate_id(30, SECRET_KEY_CHAR_SET)
REFRESH_SECRET_KEY = generate_id(30, SECRET_KEY_CHAR_SET)


class TokenPayload(NFVCLBaseModel):
    """
    Data model for the payload of a token.

    Attributes:
        username (str): The username of the user.
        iat (datetime): Issued at time.
        exp (datetime): Expiration time.
        algorithm (str): The algorithm used for hashing, default is USER_TOKEN_HASH_ALGORITHM.
    """
    username: str
    iat: datetime
    exp: datetime
    algorithm: str = USER_TOKEN_HASH_ALGORITHM


def generate_tokens_payload(username) -> tuple[TokenPayload, TokenPayload]:
    """
    Generates access and refresh token payloads.

    Args:
        username (str): The username of the user.

    Returns:
        tuple[TokenPayload, TokenPayload]: The access and refresh token payloads.
    """
    access_payload = TokenPayload(username=username, iat=datetime.now(timezone.utc), exp=datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_payload = TokenPayload(username=username, iat=datetime.now(timezone.utc), exp=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    return access_payload, refresh_payload


def generate_tokens(access_payload: TokenPayload, refresh_payload: TokenPayload) -> tuple[str, str]:
    """
    Generates access and refresh tokens.

    Args:
        access_payload (TokenPayload): The payload for the access token.
        refresh_payload (TokenPayload): The payload for the refresh token.

    Returns:
        tuple[str, str]: The access and refresh tokens.
    """
    access_token = jwt.encode(access_payload.model_dump(), SECRET_KEY, algorithm=USER_TOKEN_HASH_ALGORITHM)
    refresh_token = jwt.encode(refresh_payload.model_dump(), REFRESH_SECRET_KEY, algorithm=USER_TOKEN_HASH_ALGORITHM)

    return access_token, refresh_token


def create_tokens_for_user(user: User) -> tuple[str, str]:
    """
    Creates access and refresh tokens for a user and updates the user's token information.

    Args:
        user (User): The user object.

    Returns:
        tuple[str, str]: The access and refresh tokens.
    """
    access_payload, refresh_payload = generate_tokens_payload(user.username)
    user.access_token_expiration = access_payload.exp
    user.refresh_token_expiration = refresh_payload.exp
    access_token, refresh_token = generate_tokens(access_payload, refresh_payload)
    hash_function = getattr(hashlib, DB_TOKEN_HASH_ALGORITHM)
    user.access_token_hashed = hash_function(access_token.encode()).hexdigest()
    user.refresh_token_hashed = hash_function(refresh_token.encode()).hexdigest()
    user.access_token_hash_algorithm = DB_TOKEN_HASH_ALGORITHM
    user.refresh_token_hash_algorithm = DB_TOKEN_HASH_ALGORITHM
    return access_token, refresh_token


def decode_token(token: str, secret_key: str) -> TokenPayload | None:
    """
    Decodes and validates a JWT token.

    Args:
        token (str): The JWT token to decode.
        secret_key: The secret key to use for decoding.

    Returns:
        TokenPayload | None: The decoded payload if valid, None otherwise.
    """
    try:
        # Decode the token
        decoded_payload = jwt.decode(token, secret_key, algorithms=[USER_TOKEN_HASH_ALGORITHM])
        return TokenPayload.model_validate(decoded_payload)
    except ExpiredSignatureError:
        return None
    except JWTError:
        return None


def decode_access_token(token) -> TokenPayload | None:
    """
    Decodes and validates an access token.

    Args:
        token (str): The access token to decode.

    Returns:
        TokenPayload | None: The decoded payload if valid, None otherwise.
    """
    return decode_token(token, SECRET_KEY)


def decode_refresh_token(token) -> TokenPayload | None:
    """
    Decodes and validates an access token.

    Args:
        token (str): The access token to decode.

    Returns:
        TokenPayload | None: The decoded payload if valid, None otherwise.
    """
    return decode_token(token, REFRESH_SECRET_KEY)
