from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TypeVar, Optional, Generic, List, Dict, Any

from pydantic import Field, SerializeAsAny, field_validator, ValidationError

from nfvcl_core.utils.blue_utils import get_class_from_path
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.prometheus.prometheus_model import PrometheusTargetModel
from nfvcl_core_models.providers.providers import BlueprintNGProviderData
from nfvcl_core_models.resources import Resource

StateTypeVar = TypeVar("StateTypeVar")
CreateConfigTypeVar = TypeVar("CreateConfigTypeVar")


class CurrentOperation(Enum):
    UNDEFINED = ""
    IDLE = "idle"
    DEPLOYING = "deploying"
    RUNNING_DAY2_OP = "running-day2-op"
    DESTROYING = "destroying"

class RegisteredBlueprintCall(NFVCLBaseModel):
    """
    Store the call that have been made to the blueprint instance
    """
    function_name: str = Field(description="Name of the function")
    extra: Dict[str, str] = Field(description="Extra fields given to the function like args or kwargs", default_factory=dict)
    msg: dict = Field(description="Message of the call, given by the user", default_factory=dict)


class BlueprintNGStatus(NFVCLBaseModel):
    error: bool = Field(default=False)
    current_operation: CurrentOperation = Field(CurrentOperation.IDLE)
    detail: str = Field(default="")

    @classmethod
    def deploying(cls, blue_id) -> BlueprintNGStatus:
        return BlueprintNGStatus(current_operation=CurrentOperation.DEPLOYING, detail=f"The blueprint {blue_id} is being deployed...")

    @classmethod
    def destroying(cls, blue_id) -> BlueprintNGStatus:
        return BlueprintNGStatus(current_operation=CurrentOperation.DESTROYING, detail=f"The blueprint {blue_id} is being destroyed...")

    @classmethod
    def running_day2(cls) -> BlueprintNGStatus:
        return BlueprintNGStatus(current_operation=CurrentOperation.IDLE, detail=f"Running day2 operation...")

    @classmethod
    def idle(cls) -> BlueprintNGStatus:
        return BlueprintNGStatus(current_operation=CurrentOperation.IDLE, detail=f"Waiting for further operations")

    @classmethod
    def error_state(cls, error_detail: str) -> BlueprintNGStatus:
        return BlueprintNGStatus(current_operation=CurrentOperation.IDLE, error=True, detail=error_detail)


class BlueprintNGCreateModel(NFVCLBaseModel):
    pass

class RegisteredResource(NFVCLBaseModel):
    type: str = Field()
    value: SerializeAsAny[Resource] = Field()


class BlueprintNGProviderModel(NFVCLBaseModel):
    # area_id: Optional[int] = Field(default=None)
    provider_type: Optional[str] = Field(default=None)
    provider_data_type: Optional[str] = Field(default=None)
    # Provider data, contain information that allow the provider to correlate blueprint resources with deployed resources
    provider_data: Optional[SerializeAsAny[BlueprintNGProviderData]] = Field(default=None)


class BlueprintNGBaseModel(NFVCLBaseModel, Generic[StateTypeVar, CreateConfigTypeVar]):
    id: str = Field()
    type: str = Field()

    parent_blue_id: Optional[str] = Field(default=None)
    children_blue_ids: List[str] = Field(default_factory=list)

    # Store every resource that a blueprint manage
    registered_resources: Dict[str, RegisteredResource] = Field(default={})

    # Blueprint state, should contain running configuration and reference to resources
    state_type: str = Field()
    state: StateTypeVar = Field()

    # Initial config for the blueprint, may be used in the future for a reset functionality
    create_config_type: Optional[str] = Field(default=None)
    create_config: Optional[CreateConfigTypeVar] = Field(default=None)

    # Providers (the key is str because MongoDB doesn't support int as key for dictionary)
    # providers_data: List[BlueprintNGProviderModel] = Field(default_factory=list) # SerializeAsAny[BlueprintNGProviderModel]
    virt_providers: Dict[str, BlueprintNGProviderModel] = Field(default_factory=dict)
    k8s_providers: Dict[str, BlueprintNGProviderModel] = Field(default_factory=dict)
    pdu_provider: Optional[BlueprintNGProviderModel] = Field(default=None)
    blueprint_provider: Optional[BlueprintNGProviderModel] = Field(default=None)

    created: Optional[datetime] = Field(default=None)
    corrupted: bool = Field(default=False)
    protected: bool = Field(default=False)
    status: BlueprintNGStatus = Field(default=BlueprintNGStatus())

    node_exporters: List[PrometheusTargetModel] = Field(default=[], description="List of node exporters (for prometheus) active in the blueprint.")

    day_2_call_history: List[RegisteredBlueprintCall] = Field(default=[], description="The history of calls that have been made to the blueprint instance")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**self.fix_types(["state", "provider_data", "create_config"], **kwargs))

    def fix_types(self, field_names: List[str], **kwargs: Any):
        """
        Pydantic deserialize as parent class, this override the value deserializing as the correct class
        Require the class type to be saved as a field in the Class
        Args:
            field_names: List of fields to fix
            **kwargs: Constructor kwargs

        Returns: Fixed kwargs
        """
        for field_name in field_names:
            if field_name in kwargs:
                field_value = kwargs[field_name]
                if isinstance(field_value, dict):
                    kwargs[field_name] = get_class_from_path(kwargs[f"{field_name}_type"]).model_validate(field_value)
        return kwargs

    @field_validator('day_2_call_history', mode='before')
    def validate_items(cls, v):
        if not isinstance(v, list):
            raise ValueError('items must be a list')
        valid_items = []
        for item in v:
            try:
                valid_items.append(RegisteredBlueprintCall(**item))
            except ValidationError:
                continue
        return valid_items


class BlueprintNGState(NFVCLBaseModel):
    last_update: Optional[datetime] = Field(default=None)

class BlueprintNGException(Exception):
    pass
