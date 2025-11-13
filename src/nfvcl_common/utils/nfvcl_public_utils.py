from typing import Optional, Callable

from pydantic import Field

from nfvcl_common.base_model import NFVCLBaseModel


class NFVCLPublicSectionModel(NFVCLBaseModel):
    name: str = Field()
    description: str = Field()
    path: str = Field()

class NFVCLPublicModel(NFVCLBaseModel):
    path: str = Field()
    method: str = Field()
    section: NFVCLPublicSectionModel = Field()
    sync: bool = Field(default=False)
    summary: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)


class NFVCLPublic:
    order: int = 0

    def __init__(self, path: str, method: str, section: NFVCLPublicSectionModel, sync: bool = False, doc_by: Optional[Callable] = None, summary: Optional[str] = None, description: Optional[str] = None):
        self.path = path
        self.method = method
        self.section = section
        self.sync = sync
        self.doc_override = doc_by.__doc__ if doc_by else None
        self.summary = summary
        self.description = description

    def __call__(self, func):
        if self.doc_override:
            func.__doc__ = self.doc_override
        func.nfvcl_public = NFVCLPublicModel(path=self.path, method=self.method, section=self.section, sync=self.sync, summary=self.summary, description=self.description)
        func.order = NFVCLPublic.order
        NFVCLPublic.order += 1
        return func
