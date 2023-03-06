from pydantic import BaseModel


class HelmRepo(BaseModel):
    name: str
    description: str
    version: str
