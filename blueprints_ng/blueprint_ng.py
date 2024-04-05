from __future__ import annotations

import abc
import copy
import sys
import uuid
from datetime import datetime
from enum import Enum
from typing import Callable, TypeVar, Generic, Optional, List, Any, Dict

from fastapi import APIRouter, Request
from pydantic import SerializeAsAny, Field, ConfigDict

from blueprints_ng.lcm.blueprint_route_manager import get_module_routes
from blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderData
from blueprints_ng.providers.kubernetes import K8SProviderNative
from blueprints_ng.providers.kubernetes.k8s_provider_interface import K8SProviderInterface
from blueprints_ng.providers.virtualization import VirtualizationProviderOpenstack, VirtualizationProviderProxmox
from blueprints_ng.providers.virtualization.virtualization_provider_interface import VirtualizationProviderInterface
from blueprints_ng.resources import Resource, ResourceConfiguration, ResourceDeployable, VmResource, HelmChartResource, \
    VmResourceConfiguration, NetResource
from blueprints_ng.utils import get_class_from_path, get_class_path_str_from_obj
from models.base_model import NFVCLBaseModel
from models.prometheus.prometheus_model import PrometheusTargetModel
from models.vim import VimTypeEnum
from utils.database import save_ng_blue, destroy_ng_blue
from utils.log import create_logger

StateTypeVar = TypeVar("StateTypeVar")
CreateConfigTypeVar = TypeVar("CreateConfigTypeVar")


class BlueprintNGStatus(NFVCLBaseModel):
    error: bool = Field(default=False)
    current_operation: str = Field(default="")
    detail: str = Field(default="")


class BlueprintNGCreateModel(NFVCLBaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Allow creating model object using the field name instead of the alias
        use_enum_values=True,  # Needed to be able to save the state to the mongo DB
        validate_default=True
    )


class RegisteredResource(NFVCLBaseModel):
    type: str = Field()
    value: SerializeAsAny[Resource] = Field()


class BlueprintNGProviderModel(NFVCLBaseModel):
    provider_type: Optional[str] = Field(default=None)
    provider_data_type: Optional[str] = Field(default=None)
    # Provider data, contain information that allow the provider to correlate blueprint resources with deployed resources
    provider_data: Optional[SerializeAsAny[BlueprintNGProviderData]] = Field(default=None)


class BlueprintNGBaseModel(NFVCLBaseModel, Generic[StateTypeVar, CreateConfigTypeVar]):
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

    # Providers (the key is str because MongoDB doesn't support int as key for dictionary)
    virt_providers: Dict[str, BlueprintNGProviderModel] = Field(default_factory=dict)
    k8s_providers: Dict[str, BlueprintNGProviderModel] = Field(default_factory=dict)

    created: Optional[datetime] = Field(default=None)
    status: BlueprintNGStatus = Field(default=BlueprintNGStatus())

    node_exporters: List[PrometheusTargetModel] = Field(default=[], description="List of node exporters (for prometheus) active in the blueprint.")

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


class BlueprintNGState(NFVCLBaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # Allow creating model object using the field name instead of the alias
        use_enum_values=True,  # Needed to be able to save the state to the mongo DB
        validate_default=True
    )
    last_update: Optional[datetime] = Field(default=None)


class BlueprintNGException(Exception):
    pass


class ProvidersAggregator(VirtualizationProviderInterface, K8SProviderInterface):
    def init(self):
        pass

    def __init__(self, blueprint):
        super().__init__(-1, blueprint)

        self.virt_providers_impl: Dict[int, VirtualizationProviderInterface] = {}
        self.k8s_providers_impl: Dict[int, K8SProviderInterface] = {}

    def get_virt_provider(self, area: int):
        vim = self.topology.get_vim_from_area_id_model(area)
        if area not in self.virt_providers_impl:
            if vim.vim_type is VimTypeEnum.OPENSTACK:
                self.virt_providers_impl[area] = VirtualizationProviderOpenstack(area, self.blueprint)
            elif vim.vim_type is VimTypeEnum.PROXMOX:
                self.virt_providers_impl[area] = VirtualizationProviderProxmox(area, self.blueprint)

            self.blueprint.base_model.virt_providers[str(area)] = BlueprintNGProviderModel(
                provider_type=get_class_path_str_from_obj(self.virt_providers_impl[area]),
                provider_data_type=get_class_path_str_from_obj(self.virt_providers_impl[area].data),
                provider_data=self.virt_providers_impl[area].data
            )

        return self.virt_providers_impl[area]

    def get_k8s_provider(self, area: int):
        if area not in self.k8s_providers_impl:
            self.k8s_providers_impl[area] = K8SProviderNative(area, self.blueprint)

            self.blueprint.base_model.k8s_providers[str(area)] = BlueprintNGProviderModel(
                provider_type=get_class_path_str_from_obj(self.k8s_providers_impl[area]),
                provider_data_type=get_class_path_str_from_obj(self.k8s_providers_impl[area].data),
                provider_data=self.k8s_providers_impl[area].data
            )

        return self.k8s_providers_impl[area]

    def create_vm(self, vm_resource: VmResource):
        return self.get_virt_provider(vm_resource.area).create_vm(vm_resource)

    def create_net(self, net_resource: NetResource):
        return self.get_virt_provider(net_resource.area).create_net(net_resource)

    def configure_vm(self, vm_resource_configuration: VmResourceConfiguration) -> dict:
        return self.get_virt_provider(vm_resource_configuration.vm_resource.area).configure_vm(vm_resource_configuration)

    def destroy_vm(self, vm_resource: VmResource):
        return self.get_virt_provider(vm_resource.area).destroy_vm(vm_resource)

    def final_cleanup(self):
        for virt_provider_impl in self.virt_providers_impl.values():
            virt_provider_impl.final_cleanup()
        for k8s_provider_impl in self.k8s_providers_impl.values():
            k8s_provider_impl.final_cleanup()

    def install_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        return self.get_k8s_provider(helm_chart_resource.area).install_helm_chart(helm_chart_resource, values)

    def update_values_helm_chart(self, helm_chart_resource: HelmChartResource, values: Dict[str, Any]):
        return self.get_k8s_provider(helm_chart_resource.area).update_values_helm_chart(helm_chart_resource, values)

    def uninstall_helm_chart(self, helm_chart_resource: HelmChartResource):
        return self.get_k8s_provider(helm_chart_resource.area).uninstall_helm_chart(helm_chart_resource)


class BlueprintNG(Generic[StateTypeVar, CreateConfigTypeVar]):
    base_model: BlueprintNGBaseModel[StateTypeVar, CreateConfigTypeVar]
    api_router: APIRouter
    provider: ProvidersAggregator
    api_day0_function: Callable
    api_day2_function: Callable

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = None):
        """
        Initialize the blueprint, state_type appear to be optional to trick Python type system (see from_db), when overriding this class
        it is required.

        Args:
            blueprint_id: The ID of the blueprint instance
            state_type: The type of state for the blueprint type
        """
        super().__init__()
        self.logger = create_logger(self.__class__.__name__, blueprintid=blueprint_id)

        self.state_type = state_type
        state = state_type()
        self.base_model = BlueprintNGBaseModel[StateTypeVar, CreateConfigTypeVar](
            id=blueprint_id,
            type=get_class_path_str_from_obj(self),
            state_type=get_class_path_str_from_obj(state),
            state=state,
            created=datetime.now()
        )

        self.provider = ProvidersAggregator(self)

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

    def deregister_resource(self, resource: Resource):
        """
        Remove a resource in the blueprint registered resources
        Args:
            resource: the resource to be deregistered
        """
        if not resource.id:
            raise BlueprintNGException(f"The ID of the resource to be deleted is None")
        if resource.id in self.base_model.registered_resources:
            self.base_model.registered_resources.pop(resource.id)
        else:
            raise BlueprintNGException(f"The resource to be deleted is not present in registered resources")

    def create(self, model: CreateConfigTypeVar):
        self.base_model.create_config = model
        self.base_model.create_config_type = get_class_path_str_from_obj(model)

    def destroy(self):
        for key, value in self.base_model.registered_resources.items():
            if isinstance(value.value, VmResource):
                self.provider.destroy_vm(value.value)
            elif isinstance(value.value, HelmChartResource):
                self.provider.uninstall_helm_chart(value.value)
        self.provider.final_cleanup()
        destroy_ng_blue(blueprint_id=self.base_model.id)

    @property
    def state(self) -> StateTypeVar:
        return self.base_model.state

    @property
    def id(self) -> str:
        return self.base_model.id

    @property
    def create_config(self) -> CreateConfigTypeVar:
        return self.base_model.create_config

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

        if isinstance(obj, Enum):
            pass
        elif isinstance(obj, dict):
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

    def __serialize_content(self) -> dict:
        serialized_dict = self.base_model.model_dump()

        # Find every occurrence of type Resource in the state amd replace them with a reference
        self.__override_variables_in_dict(self.base_model.state, serialized_dict["state"], Resource)

        # Find every occurrence of type ResourceConfiguration in the registered_resources and replace the ResourceDeployable field with a reference
        for key, value in self.base_model.registered_resources.items():
            if isinstance(value.value, ResourceConfiguration):
                self.__override_variables_in_dict(value.value, serialized_dict["registered_resources"][key]["value"], ResourceDeployable)

        return serialized_dict

    def to_db(self) -> None:
        """
        Generates the blueprint serialized representation and save it in the database.
        """
        self.logger.debug("to_db")
        serialized_dict = self.__serialize_content()
        save_ng_blue(self.base_model.id, serialized_dict)

    @classmethod
    def from_db(cls, deserialized_dict: dict):
        BlueSavedClass = get_class_from_path(deserialized_dict['type'])
        instance = BlueSavedClass(deserialized_dict['id'])

        # Remove fields that need to be manually deserialized from the input and validate
        deserialized_dict_edited = copy.deepcopy(deserialized_dict)
        del deserialized_dict_edited["registered_resources"]
        deserialized_dict_edited["state"] = instance.state_type().model_dump()
        instance.base_model = BlueprintNGBaseModel[StateTypeVar, CreateConfigTypeVar].model_validate(deserialized_dict_edited)

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

        # Loading the providers data
        # get_virt_provider is used to create a new instance of the provider for the area
        for area, virt_provider in deserialized_dict["virt_providers"].items():
            instance.provider.get_virt_provider(int(area)).data = instance.provider.get_virt_provider(int(area)).data.model_validate(virt_provider["provider_data"])

        for area, k8s_provider in deserialized_dict["k8s_providers"].items():
            instance.provider.get_k8s_provider(int(area)).data = instance.provider.get_k8s_provider(int(area)).data.model_validate(k8s_provider["provider_data"])

        return instance

    def to_dict(self, detailed: bool) -> dict:
        """
        Return a dictionary representation of the blueprint instance.

        Args:
            detailed: Return the same content saved in the database containing all the details of the blueprint.

        Returns:

        """
        if detailed:
            return self.__serialize_content()
        else:
            return {"id": self.base_model.id, "type": self.base_model.type, "status": self.base_model.status, "created": self.base_model.created}

    @classmethod
    @abc.abstractmethod
    def rest_create(cls, msg: dict, request: Request):
        pass

    @classmethod
    def init_router(cls, _day0_func: Callable, _day2_func: Callable, prefix: str) -> APIRouter:
        """
        Initialize the blueprint router and register apis to it.
        Args:
            _day0_func: The function to be pointed for blueprint creation
            _day2_func: The function that will handle all day-2 operations
            prefix: The prefix that all the APIs declared in the blueprint will have.

        Returns:
            The created and configured router.
        """
        cls.api_day0_function = _day0_func
        cls.api_day2_function = _day2_func
        cls.api_router = APIRouter(
            prefix=f"/{prefix}",
            tags=[f"Blueprint {cls.__name__}"],
            responses={404: {"description": "Not found"}}
        )
        cls.api_router.add_api_route("", cls.rest_create, methods=["POST"])

        # The prefix is the base path of the module, e.g., 'api_common_url/vyos/create' -> prefix = 'vyos'
        for day2_route in get_module_routes(prefix):
            fake_endpoint = day2_route.fake_endpoint
            module_location = fake_endpoint.__module__
            module = sys.modules[module_location]
            func_class, func_name = day2_route.fake_endpoint.__func__.__qualname__.split('.')
            class_obj = getattr(module, func_class)
            bound_method = getattr(class_obj, func_name)

            cls.api_router.add_api_route(day2_route.final_path, bound_method, methods=day2_route.get_methods_str())

        return cls.api_router

    def call_external_function(self, external_blue_id: str, function_name: str, *args, **kwargs):
        """
        Call a function on another blueprint
        Args:
            external_blue_id: Id of the blueprint to call on the function on
            function_name: Name of the function to call
            *args: args
            **kwargs: kwargs

        Returns: Result of the function call
        """
        from rest_endpoints.blue_ng_router import get_blueprint_manager

        self.logger.debug(f"Calling external function '{function_name}' on blueprint '{external_blue_id}', args={args}, kwargs={kwargs}")
        res = get_blueprint_manager().get_worker(external_blue_id).call_function_sync(function_name, *args, **kwargs)
        self.logger.debug(f"Result of external function '{function_name}' on blueprint '{external_blue_id}' = {res}")
        return res
