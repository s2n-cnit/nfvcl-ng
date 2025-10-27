from typing import Optional

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel


class LokiServerModel(NFVCLBaseModel):
    """
    Models a Loki server instance to be managed.
    """
    id: str
    ip: str = Field(default='127.0.0.1')
    port: str = Field(default='3100')
    user: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)

    def __eq__(self, other):
        """
        Overrides the default equals implementation.
        In this way, it is possible to directly compare objects
        of this type on a given criteria (in this case the id)
        """
        if isinstance(other, LokiServerModel):
            return self.id == other.id
        return False
