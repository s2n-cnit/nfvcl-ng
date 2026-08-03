from pydantic import ConfigDict, Field, SerializeAsAny

from nfvcl_common.base_model import NFVCLBaseModel


class ProviderData(NFVCLBaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Allow creating model object using the field name instead of the alias
        extra="allow" # Allow extra fields, needed because we don't know the provider data type when deserializing
    )

class ProviderException(Exception):
    pass


class ProviderDataDocument(NFVCLBaseModel):
    provider_type: str
    data: SerializeAsAny[ProviderData] = Field(default_factory=ProviderData)
