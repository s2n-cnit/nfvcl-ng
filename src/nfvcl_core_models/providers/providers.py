from typing import Dict, Optional

from pydantic import ConfigDict, Field, SerializeAsAny

from nfvcl_common.base_model import NFVCLBaseModel


class BlueprintNGProviderData(NFVCLBaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Allow creating model object using the field name instead of the alias
        extra="allow" # Allow extra fields, needed because we don't know the provider data type when deserializing
    )

class BlueprintNGProviderModel(NFVCLBaseModel):
    provider_type: Optional[str] = Field(default=None)
    provider_data_type: Optional[str] = Field(default=None)
    # Provider data, contain information that allow the provider to correlate blueprint resources with deployed resources
    provider_data: Optional[SerializeAsAny[BlueprintNGProviderData]] = Field(default=None)

class ProviderDataAggregate(NFVCLBaseModel):
    blueprint_id: str = Field()
    # Providers (the key is str because MongoDB doesn't support int as key for dictionary)
    virtualization: Optional[Dict[str, BlueprintNGProviderModel]] = Field(default_factory=dict)
    k8s: Optional[Dict[str, BlueprintNGProviderModel]] = Field(default_factory=dict)
    pdu: Optional[BlueprintNGProviderModel] = Field(default=None)
    blueprint: Optional[BlueprintNGProviderModel] = Field(default=None)

class BlueprintNGProviderException(Exception):
    pass
