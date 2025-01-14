from typing import List

from pydantic import Field

from nfvcl_core.models.providers.providers import BlueprintNGProviderData


class BlueprintProviderData(BlueprintNGProviderData):
    deployed_blueprints: List[str] = Field(default_factory=list)


class BlueprintProviderException(Exception):
    pass
