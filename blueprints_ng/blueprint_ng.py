from __future__ import annotations

import copy
import importlib
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Callable, TypeVar, Generic, Optional, List, Any, Dict

from fastapi import APIRouter
from pydantic import SerializeAsAny, Field

from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface
from blueprints_ng.resources import Resource, ResourceConfiguration, ResourceDeployable, VmResource
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


def get_class_path_str_from_obj(obj: Any) -> str:
    return f"{obj.__class__.__module__}.{obj.__class__.__qualname__}"


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
    create_config_type: Optional[str] = Field(default=None)
    create_config: Optional[CreateConfigTypeVar] = Field(default=None)

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
            if field_name in kwargs:
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


class BlueprintNGException(Exception):
    pass


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
                type=get_class_path_str_from_obj(self),
                state_type=get_class_path_str_from_obj(state),
                state=state,
                provider_type=get_class_path_str_from_obj(self.provider),
                provider_data_type=get_class_path_str_from_obj(self.provider.data),
                provider_data=self.provider.data
            )

    def register_resource(self, resource: Resource):
        """
        Register a resource in the blueprint, this is mandatory
        Args:
            resource: the resource to be registered
        """
        if resource.id and resource.id in self.base_model.registered_resources:
            raise BlueprintNGException(f"Already registered")
        if not resource.id:
            resource.id = str(uuid.uuid4())
        self.base_model.registered_resources[resource.id] = RegisteredResource(type=get_class_path_str_from_obj(resource), value=resource)

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

    def create(self, model: CreateConfigTypeVar):
        self.base_model.create_config = model
        self.base_model.create_config_type = get_class_path_str_from_obj(model)

    def destroy(self):
        for key, value in self.base_model.registered_resources.items():
            if isinstance(value.value, VmResource):
                self.provider.destroy_vm(value.value)

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
        """
        Replace every Resource with its reference ID within the object.

        Args:
            obj: The object in witch reference are searched
            obj_dict: The dictionary in witch the references are replaced with their object reference ID
            tipo: The (filter) type of the objects to be replaced in the dict
        """
        # Getting a tuple list of path inside the object to be replaced with reference ID
        occ = self.__find_field_occurrences(obj, tipo)
        # Replacing every object in the list with its reference id
        for path in sorted(occ, key=lambda x: len(x), reverse=True):  # Ordered because replace inner ref in advance
            current = obj_dict
            for key in path[:-1]:  # This is done because cannot perform path[:-1][a][b][c].... dynamically
                current = current[key]
            # Replacing the object with its reference ID
            current[path[-1]] = f'REF={current[path[-1]]["id"]}'

    def __override_variables_in_dict_ref(self, obj, obj_dict, registered_resource):
        occ = self.__find_field_occurrences(obj, type_to_find=str, check_fun=lambda x: x.startswith('REF='))
        for path in sorted(occ, key=lambda x: len(x), reverse=True):
            current = obj_dict
            for key in path[:-1]:
                current = current[key]
            current[path[-1]] = registered_resource[current[path[-1]].split("REF=")[1]].value

    def to_db(self):
        """
        TODO complete. Temporaly return a json that represent what is going to be saved in the DB
        Returns:

        """
        serialized_dict = self.base_model.model_dump()

        # Find every occurrence of type Resource in the state amd replace them with a reference
        self.__override_variables_in_dict(self.base_model.state, serialized_dict["state"], Resource)

        # Find every occurrence of type ResourceConfiguration in the registered_resources and replace the ResourceDeployable field with a reference
        for key, value in self.base_model.registered_resources.items():
            if isinstance(value.value, ResourceConfiguration):
                self.__override_variables_in_dict(value.value, serialized_dict["registered_resources"][key]["value"], ResourceDeployable)

        return json.dumps(serialized_dict, indent=4)

    @classmethod
    def from_db(cls, serialized: str):
        deserialized_dict = json.loads(serialized)

        # Manually load state and provider classes
        state_type_str = deserialized_dict["state_type"]
        provider_type_str = deserialized_dict["provider_type"]
        state_type = get_class_from_path(state_type_str)
        provider_type = get_class_from_path(provider_type_str)

        # Create a new instance
        instance = cls(provider_type, state_type)

        # Remove fields that need to be manually deserialized from the input and validate
        deserialized_dict_edited = copy.deepcopy(deserialized_dict)
        del deserialized_dict_edited["registered_resources"]
        deserialized_dict_edited["state"] = instance.state_type().model_dump()
        instance.base_model = BlueprintNGBaseModel[StateTypeVar, ProviderDataTypeVar, CreateConfigTypeVar].model_validate(deserialized_dict_edited)

        # Register the reloaded resources of type ResourceDeployable
        for resource_id, resource in deserialized_dict["registered_resources"].items():
            if resource["value"]["type"] == "ResourceDeployable":
                instance.register_resource(get_class_from_path(resource["type"]).model_validate(resource["value"]))

        # Register the reloaded resources of type ResourceConfiguration, also resolve the references within and link them to the same object instance registered above
        for resource_id, resource in deserialized_dict["registered_resources"].items():
            if resource["value"]["type"] == "ResourceConfiguration":
                instance.__override_variables_in_dict_ref(resource["value"], resource["value"], instance.base_model.registered_resources)
                instance.register_resource(get_class_from_path(resource["type"]).model_validate(resource["value"]))

        # Here the registered_resources should be in the same state as before saving the blueprint to the db

        # Resolve all reference in the state
        instance.__override_variables_in_dict_ref(deserialized_dict["state"], deserialized_dict["state"], instance.base_model.registered_resources)

        # Deserialized remaining fields in the state and override the field in base_model
        instance.base_model.state = instance.state_type.model_validate(deserialized_dict["state"])
        instance.provider.data = instance.provider_data.model_validate(deserialized_dict["provider_data"])
        return instance
