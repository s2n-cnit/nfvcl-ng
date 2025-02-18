from typing import Any, List

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel


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
    schema_osm: str = Field(alias="schema")

class ImageRepo(NFVCLBaseModel):
    name: str
    to_download: bool = Field(default=False, description="If the image needs to be downloaded or not(Some need to be uploaded manually)")
    url: str

    def __eq__(self, other):
        """
        Overrides the default equals implementation. In this way, it is possible to directly compare objects
        of this type on a given criteria (in this case the 'name')
        """
        if isinstance(other, ImageRepo):
            if self.name == other.name:
                return True
        return False

    def __str__(self):
        return f"{self.name}"
class ImageList(NFVCLBaseModel):
    images: List[ImageRepo]
