from pydantic import ConfigDict

from nfvcl_core.models.base_model import NFVCLBaseModel


class BlueprintNGProviderData(NFVCLBaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Allow creating model object using the field name instead of the alias
        extra="allow" # Allow extra fields, needed because we don't know the provider data type when deserializing
    )
    pass


class BlueprintNGProviderException(Exception):
    pass
