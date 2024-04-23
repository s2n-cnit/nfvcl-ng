from typing import List

from pydantic import Field

from blueprints_ng.blueprint_ng import BlueprintNGCreateModel


class DNSCreateModel(BlueprintNGCreateModel):
    """
    This class represents the model for the creation request
    """
    password: str = Field(default="ubuntu", description="The password to be set", pattern=r'^[a-zA-Z0-9_.-]*$')
    mgmt_net: str = Field(description="The management network of the DNS server")
    data_nets: List[str] = Field(default=[], description="The data network to be connected at DNS server")
    area: int = Field(description="The area in witch the VM is deployed")
