import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import Field, field_validator

from nfvcl_core.models.base_model import NFVCLBaseModel


class UserRole(str, Enum):
    """
    Supported plugin names by the k8s manager
    """
    ADMIN = 'admin'
    USER = 'user'


class User(NFVCLBaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str = Field()
    password_hash: str = Field()
    email: Optional[str] = Field(default=None)
    role: UserRole = Field(default=UserRole.USER)
    created_at: datetime = Field(default=datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default=None)

    @field_validator('password_hash', mode='before')
    def hash_password_validator(cls, password):
        if len(password) == 64 and all(c in '0123456789abcdef' for c in password):
            return password
        return hashlib.sha256(password.encode()).hexdigest()
