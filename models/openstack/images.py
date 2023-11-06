from typing import Any, List
from models.base_model import NFVCLBaseModel


class OpenStackImage(NFVCLBaseModel):
    name: str
    disk_format: str
    container_format: str | None
    visibility: str
    size: Any
    virtual_size: Any
    status: str
    checksum: Any
    protected: bool
    min_ram: int
    min_disk: int
    owner: Any
    os_hidden: bool
    os_hash_algo: Any
    os_hash_value: Any
    id: str
    created_at: str
    updated_at: str
    tags: List
    self: str
    file: str
    schema: str # TODO SHADOW AN INTERNAL PYDANTIC VALUE

class ImageRepo(NFVCLBaseModel):
    name: str
    url: str

class ImageList(NFVCLBaseModel):
    images: List[ImageRepo]
