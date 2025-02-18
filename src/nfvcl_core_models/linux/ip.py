from typing import Optional

from pydantic import Field

from nfvcl_core_models.base_model import NFVCLBaseModel


class Route(NFVCLBaseModel):
    """
    This class represent a Linux route and allow to get the commands to set that route
    """
    network_cidr: str = Field()
    next_hop: str = Field()
    device: Optional[str] = Field(default=None)

    def as_linux_replace_command(self) -> str:
        command = f"ip r replace {self.network_cidr} via {self.next_hop}"
        if self.device:
            command += f" dev {self.device}"
        return command
