from typing import List, Optional

from pydantic import Field

from blueprints_ng.utils import get_yaml_parser
from models.base_model import NFVCLBaseModel


class CloudInitChpasswd(NFVCLBaseModel):
    expire: bool = Field(default=False)


class CloudInit(NFVCLBaseModel):
    manage_etc_hosts: bool = Field(default=True)
    password: str = Field()
    chpasswd: CloudInitChpasswd = Field(default=CloudInitChpasswd())
    ssh_pwauth: bool = Field(default=True)
    ssh_authorized_keys: Optional[List[str]] = Field(default=None)
    packages: Optional[List[str]] = Field(default=None)
    runcmd: Optional[List[str]] = Field(default=None)

    def build_cloud_config(self) -> str:
        return f"#cloud-config\n{get_yaml_parser().dump(self.model_dump(exclude_none=True))}"
