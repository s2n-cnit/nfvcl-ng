from __future__ import annotations

import copy
import importlib
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Callable, TypeVar, Generic, Optional, List, Any, Dict

from fastapi import APIRouter
from pydantic import SerializeAsAny, create_model, Field

from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface
from blueprints_ng.resources import Resource, ResourceConfiguration, ResourceDeployable
from models.base_model import NFVCLBaseModel

StateTypeVar = TypeVar("StateTypeVar")
ProviderDataTypeVar = TypeVar("ProviderDataTypeVar")
CreateConfigTypeVar = TypeVar("CreateConfigTypeVar")


def get_class_from_path(class_path: str) -> Any:
    """
    Get class from the give string module path
    Args:
        class_path: module path

    Returns: The class found
    """
    field_type_split = class_path.split(".")

    module_name = ".".join(field_type_split[:-1])
    class_name = field_type_split[-1]

    module = importlib.import_module(module_name)
    found_class = getattr(module, class_name)
    return found_class


class BlueprintNGStatus(NFVCLBaseModel):
    error: bool = Field(default=False)
    current_operation: str = Field(default="")
    detail: str = Field(default="")


class BlueprintNGCreateModel(NFVCLBaseModel):
    pass


class RegisteredResource(NFVCLBaseModel):
    type: str = Field()
    value: SerializeAsAny[Resource] = Field()


class BlueprintNGBaseModel(NFVCLBaseModel, Generic[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar]):
    id: str = Field()
    type: str = Field()

    # Store every resource that a blueprint manage
    registered_resources: Dict[str, RegisteredResource] = Field(default={})

    # Blueprint state, should contain running configuration and reference to resources
    state_type: str = Field()
    state: StateTypeVar = Field()

    # Initial config for the blueprint, may be used in the future for a reset functionality
    create_config_type: str = Field()
    create_config: CreateConfigTypeVar = Field()

    # Provider data, contain information that allow the provider to correlate blueprint resources with deployed resources
    provider_type: str = Field()
    provider_data_type: str = Field()
    provider_data: ProviderDataTypeVar = Field()

    created: Optional[datetime] = Field(default=None)
    status: BlueprintNGStatus = Field(default=BlueprintNGStatus())

    # TODO il tipo dovrebbe essere PrometheusTargetModel
    node_exporters: List[str] = Field(default=[], description="List of node exporters (for prometheus) active in the blueprint.")

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
            field_value = kwargs[field_name]
            if isinstance(field_value, dict):
                kwargs[field_name] = get_class_from_path(kwargs[f"{field_name}_type"]).model_validate(field_value)
        return kwargs


class HttpRequestType(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class BlueprintNGState(NFVCLBaseModel):
    last_update: Optional[datetime] = Field(default=None)


class BlueprintNG(Generic[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar]):
    base_model: BlueprintNGBaseModel[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar]
    api_router: APIRouter
    provider: BlueprintNGProviderInterface

    def __init__(self, provider_type: type[BlueprintNGProviderInterface], state_type: type[BlueprintNGState], db_data: Optional[str] = None):
        super().__init__()
        self.provider = provider_type()
        self.state_type = state_type
        if db_data is not None:
            self.base_model = BlueprintNGBaseModel.model_validate_json(db_data)
        else:
            state = state_type()
            self.base_model = BlueprintNGBaseModel[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar](
                id=str(uuid.uuid4()),
                type=f"{self.__class__.__qualname__}",
                state_type=f"{state.__class__.__module__}.{state.__class__.__qualname__}",
                state=state,
                provider_type=self.provider.__class__.__qualname__,
                provider_data_type=f"{self.provider.data.__class__.__module__}.{self.provider.data.__class__.__qualname__}",
                provider_data=self.provider.data,
                create_config=BlueprintNGCreateModel(),
                create_config_type=f"{BlueprintNGCreateModel.__module__}.{BlueprintNGCreateModel.__qualname__}"
            )

    def register_resource(self, resource: Resource):
        """
        Register a resource in the blueprint, this is mandatory
        Args:
            resource: the resource to be registered
        """
        if not resource.id:
            resource.id = str(uuid.uuid4())
        resource.set_context(self)
        self.base_model.registered_resources[resource.id] = RegisteredResource(type=f"{resource.__class__.__module__}.{resource.__class__.__qualname__}", value=resource)

    def init_blueprint_type(self):
        """
        Initialize the blueprint
        """
        self.api_router = APIRouter(
            prefix="/{}".format(self.__name__),
            tags=["Blueprint {}".format(self.__name__)],
            responses={404: {"description": "Not found"}}
        )

    def register_api(self, path: str, request_type: HttpRequestType, method: Callable):
        """
        Register a new API endpoint for this blueprint
        Args:
            path: Endpoint path
            request_type: Type of HTTP request (GET, POST, PUT, DELETE)
            method: Method to be called when the API is called
        """
        self.api_router.add_api_route(path, method, methods=[request_type.value])

    def create(self, model: BlueprintNGCreateModel):
        pass

    def destroy(self):
        pass

    @property
    def state(self) -> StateTypeVar:
        return self.base_model.state

    @property
    def create_config(self) -> CreateConfigTypeVar:
        return self.base_model.create_config

    @property
    def provider_data(self) -> ProviderDataTypeVar:
        return self.base_model.provider_data

    def __find_field_occurrences(self, obj, type_to_find, path=(), check_fun=lambda x: True):
        """
        Recursively find every occurrence of a certain field type, check_fun can be set for additional conditional check
        Args:
            obj: Starting object
            type_to_find: Type of the fields to find
            path: Current exploration path
            check_fun: Function used on the field for additional checks, should return a bool

        Returns: List of occurrences found
        """
        occurrences = []

        if isinstance(obj, type_to_find) and check_fun(obj):
            occurrences.append(path)

        if isinstance(obj, dict):
            for key, value in obj.items():
                occurrences.extend(self.__find_field_occurrences(value, type_to_find, path=(path + (key,)), check_fun=check_fun))
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                occurrences.extend(self.__find_field_occurrences(item, type_to_find, path=(path + (idx,)), check_fun=check_fun))
        elif hasattr(obj, '__dict__'):  # True when obj is an instance of a generic class
            for attr_name in vars(obj):  # vars get the fields of obj
                attr_value = getattr(obj, attr_name)
                occurrences.extend(self.__find_field_occurrences(attr_value, type_to_find, path=(path + (attr_name,)), check_fun=check_fun))

        return occurrences

    def __override_variables_in_dict(self, obj, obj_dict, tipo):
        occ = self.__find_field_occurrences(obj, tipo)
        for path in sorted(occ, key=lambda x: len(x), reverse=True):
            current = obj_dict
            for key in path[:-1]:
                current = current[key]
            current[path[-1]] = f'REF={current[path[-1]]["id"]}'

    def __override_variables_in_dict_ref(self, obj, obj_dict, registered_resource):
        occ = self.__find_field_occurrences(obj, type_to_find=str, check_fun=lambda x: x.startswith('REF='))
        for path in sorted(occ, key=lambda x: len(x), reverse=True):
            current = obj_dict
            for key in path[:-1]:
                current = current[key]
            current[path[-1]] = registered_resource[current[path[-1]].split("REF=")[1]].value

    def to_db(self):
        serialized_dict = self.base_model.model_dump()

        # Find every occurrence of type Resource in the state amd replace them with a reference
        self.__override_variables_in_dict(self.base_model.state, serialized_dict["state"], Resource)

        # Find every occurrence of type ResourceConfiguration in the registered_resources and replace the ResourceDeployable field with a reference
        for key, value in self.base_model.registered_resources.items():
            if isinstance(value.value, ResourceConfiguration):
                self.__override_variables_in_dict(value.value, serialized_dict["registered_resources"][key]["value"], ResourceDeployable)

        return json.dumps(serialized_dict, indent=4)

    def from_db(self, serialized: str):
        deserialized_dict = json.loads(serialized)

        # Remove fields that need to be manually deserialized from the input and validate
        deserialized_dict_edited = copy.deepcopy(deserialized_dict)
        del deserialized_dict_edited["registered_resources"]
        deserialized_dict_edited["state"] = self.state_type().model_dump()
        self.base_model = BlueprintNGBaseModel[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar].model_validate(deserialized_dict_edited)

        # Register the reloaded resources of type ResourceDeployable
        for resource_id, resource in deserialized_dict["registered_resources"].items():
            if resource["value"]["type"] == "ResourceDeployable":
                self.register_resource(get_class_from_path(resource["type"]).model_validate(resource["value"]))

        # Register the reloaded resources of type ResourceConfiguration, also resolve the references within and link them to the same object instance registered above
        for resource_id, resource in deserialized_dict["registered_resources"].items():
            if resource["value"]["type"] == "ResourceConfiguration":
                self.__override_variables_in_dict_ref(resource["value"], resource["value"], self.base_model.registered_resources)
                self.register_resource(get_class_from_path(resource["type"]).model_validate(resource["value"]))

        # Here the registered_resources should be in the same state as before saving the blueprint to the db

        # Resolve all reference in the state
        self.__override_variables_in_dict_ref(deserialized_dict["state"], deserialized_dict["state"], self.base_model.registered_resources)

        # Deserialized remaining fields in the state and override the field in base_model
        self.base_model.state = self.state_type.model_validate(deserialized_dict["state"])
        return self.base_model.state
