from __future__ import annotations
import copy
import uuid
from datetime import datetime
from enum import Enum
from typing import TypeVar, Generic

from pydantic import ValidationError

from nfvcl_core.models.blueprints import BlueprintNGState, BlueprintNGBaseModel, BlueprintNGException, RegisteredResource
from nfvcl_core.models.http_models import BlueprintNotFoundException
from nfvcl_core.models.resources import Resource, ResourceConfiguration, ResourceDeployable, VmResource, \
    HelmChartResource
from nfvcl_core.providers.aggregator import ProvidersAggregator
from nfvcl_core.utils.blue_utils import get_class_path_str_from_obj, get_class_from_path
from nfvcl_core.utils.log import create_logger

StateTypeVar = TypeVar("StateTypeVar")
CreateConfigTypeVar = TypeVar("CreateConfigTypeVar")


class BlueprintNG(Generic[StateTypeVar, CreateConfigTypeVar]):
    provider: ProvidersAggregator

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
        self.base_model: BlueprintNGBaseModel[StateTypeVar, CreateConfigTypeVar] = BlueprintNGBaseModel[StateTypeVar, CreateConfigTypeVar](
            id=blueprint_id,
            type=get_class_path_str_from_obj(self),
            state_type=get_class_path_str_from_obj(state),
            state=state,
            created=datetime.now()
        )

    @property
    def state(self) -> StateTypeVar:
        return self.base_model.state

    @property
    def id(self) -> str:
        return self.base_model.id

    @property
    def create_config(self) -> CreateConfigTypeVar:
        return self.base_model.create_config

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
        if isinstance(resource, ResourceDeployable):
            resource_dep: ResourceDeployable = resource
            try:
                self.provider.topology_manager.get_vim_from_area_id_model(resource_dep.area)
            except ValueError as e:
                raise BlueprintNGException("Unable to register resource, the area has no associated VIM")
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

    def deregister_resource_by_id(self, resource_id: str):
        """
        Remove a resource in the blueprint registered resources using its id
        Args:
            resource_id: the id of the resource to be deregistered
        """
        if resource_id in self.base_model.registered_resources:
            self.base_model.registered_resources.pop(resource_id)
        else:
            raise BlueprintNGException(f"The resource to be deleted is not present in registered resources")

    def get_registered_resources(self, type_filter: str = None):
        """
        Return the list of registered resources for this blueprint instance. The list can be filtered using the 'type_filter'
        Args:
            type_filter: used to filter the resources to be returned (e.g. 'blueprints_ng.resources.VmResource'). Default 'None' for no filtering.

        Returns:
            The filtered list.
        """
        if type_filter is None:
            return self.base_model.registered_resources.values()
        else:
            return [resource for resource in self.base_model.registered_resources.values() if resource.type == type_filter]

    def register_children(self, blue_id: str):
        """
        Register a blueprint id as a children of this blueprint
        Args:
            blue_id: Blueprint id to be registered as a children
        """
        if blue_id not in self.base_model.children_blue_ids:
            self.base_model.children_blue_ids.append(blue_id)
        else:
            raise BlueprintNGException(f"Children blueprint {blue_id} already present")

    def deregister_children(self, blue_id: str):
        """
        Deregister a blueprint id from being a children of this blueprint
        Args:
            blue_id: Blueprint id to be deregistered
        """
        if blue_id in self.base_model.children_blue_ids:
            self.base_model.children_blue_ids.remove(blue_id)
        else:
            raise BlueprintNGException(f"Children blueprint {blue_id} not found")

    def create(self, model: CreateConfigTypeVar):
        self.base_model.create_config = model
        self.base_model.create_config_type = get_class_path_str_from_obj(model)

    def destroy(self):
        for children_id in self.base_model.children_blue_ids.copy():
            try:
                self.provider.delete_blueprint(children_id)
            except BlueprintNotFoundException:
                self.logger.warning(f"The children blueprint {children_id} has not been found. Could be deleted before, skipping...")
            self.deregister_children(children_id)

        for key, value in self.base_model.registered_resources.items():
            if isinstance(value.value, VmResource):
                self.provider.destroy_vm(value.value)
            elif isinstance(value.value, HelmChartResource):
                self.provider.uninstall_helm_chart(value.value)
        self.provider.final_cleanup()

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
            current_id = current[path[-1]]["id"]
            if current_id in self.base_model.registered_resources:
                current[path[-1]] = f'REF={current[path[-1]]["id"]}'
            else:
                raise BlueprintNGException(f"Resource {current_id} not registered")

    def __override_variables_in_dict_ref(self, obj, obj_dict, registered_resource):
        occ = self.__find_field_occurrences(obj, type_to_find=str, check_fun=lambda x: x.startswith('REF='))
        for path in sorted(occ, key=lambda x: len(x), reverse=True):
            current = obj_dict
            for key in path[:-1]:
                current = current[key]
            current[path[-1]] = registered_resource[current[path[-1]].split("REF=")[1]].value

    def serialize_base_model(self) -> dict:
        serialized_dict = self.base_model.model_dump()

        try:
            # Find every occurrence of type Resource in the state and replace them with a reference
            self.__override_variables_in_dict(self.base_model.state, serialized_dict["state"], Resource)

            # Find every occurrence of type ResourceConfiguration in the registered_resources and replace the ResourceDeployable field with a reference
            for key, value in self.base_model.registered_resources.items():
                if isinstance(value.value, ResourceConfiguration):
                    self.__override_variables_in_dict(value.value, serialized_dict["registered_resources"][key]["value"], ResourceDeployable)
        except BlueprintNGException as e:
            self.logger.error(f"Error serializing blueprint: {str(e)}")
            serialized_dict["corrupted"] = True

        return serialized_dict

    def to_db(self) -> None:
        """
        Generates the blueprint serialized representation and save it in the database.
        """
        self.logger.debug("to_db")
        self.provider.blueprint_manager.save_blueprint(self)

    @classmethod
    def from_db(cls, deserialized_dict: dict, provider=None):
        """
        Load a blueprint from the dictionary and initialize providers.
        Args:
            deserialized_dict: The dictionary coming from the database

        Returns:
            A complete blueprint instance that can operate on the blueprint.
        """
        BlueSavedClass = get_class_from_path(deserialized_dict['type'])
        instance = BlueSavedClass(deserialized_dict['id'])

        if provider:
            provider.set_blueprint(instance)
            instance.provider = provider

        # Remove fields that need to be manually deserialized from the input and validate
        deserialized_dict_edited = copy.deepcopy(deserialized_dict)
        del deserialized_dict_edited["registered_resources"]
        deserialized_dict_edited["state"] = instance.state_type().model_dump()
        try:
            instance.base_model = BlueprintNGBaseModel[StateTypeVar, CreateConfigTypeVar].model_validate(deserialized_dict_edited)
        except ValidationError as e:
            deserialized_dict_edited["create_config"] = None
            instance.base_model = BlueprintNGBaseModel[StateTypeVar, CreateConfigTypeVar].model_validate(deserialized_dict_edited)
            instance.logger.error(f"Unable to load create_config: {str(e)}")
            instance.base_model.corrupted = True
            instance.logger.error(f"Blueprint set as corrupted")

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
        try:
            instance.base_model.state = instance.state_type.model_validate(deserialized_dict["state"])
        except ValidationError as e:
            instance.logger.error(f"Unable to load state: {str(e)}")
            instance.base_model.corrupted = True
            instance.logger.error(f"Blueprint set as corrupted")

        if provider:
            # Loading the providers data
            # get_virt_provider is used to create a new instance of the provider for the area
            for area, virt_provider in deserialized_dict["virt_providers"].items():
                provider_data = instance.provider.get_virt_provider(int(area)).data.model_validate(virt_provider["provider_data"])
                instance.provider.get_virt_provider(int(area)).data = provider_data
                instance.base_model.virt_providers[str(area)].provider_data = provider_data

            for area, k8s_provider in deserialized_dict["k8s_providers"].items():
                provider_data = instance.provider.get_k8s_provider(int(area)).data.model_validate(k8s_provider["provider_data"])
                instance.provider.get_k8s_provider(int(area)).data = provider_data
                instance.base_model.k8s_providers[str(area)].provider_data = provider_data

            if "pdu_provider" in deserialized_dict:
                pdu_provider = deserialized_dict["pdu_provider"]
                if pdu_provider:
                    provider_data = instance.provider.get_pdu_provider().data.model_validate(pdu_provider["provider_data"])
                    instance.provider.get_pdu_provider().data = provider_data
                    instance.base_model.pdu_provider.provider_data = provider_data

            if "blueprint_provider" in deserialized_dict:
                blueprint_provider = deserialized_dict["blueprint_provider"]
                if blueprint_provider:
                    provider_data = instance.provider.get_blueprint_provider().data.model_validate(blueprint_provider["provider_data"])
                    instance.provider.get_blueprint_provider().data = provider_data
                    instance.base_model.blueprint_provider.provider_data = provider_data

        return instance

    def to_dict(self, detailed: bool) -> dict:
        """
        Return a dictionary representation of the blueprint instance.

        Args:
            detailed: Return the same content saved in the database containing all the details of the blueprint.

        Returns:

        """
        if detailed:
            return self.serialize_base_model()
        else:
            dict_to_ret = {"id": self.base_model.id, "type": self.base_model.type, "status": self.base_model.status, "created": self.base_model.created, "protected": self.base_model.protected}
            if self.base_model.corrupted:
                dict_to_ret["corrupted"] = True
            return dict_to_ret

