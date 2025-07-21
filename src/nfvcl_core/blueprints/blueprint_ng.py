from __future__ import annotations

import copy
import json
import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import TypeVar, Generic, Optional

from pydantic import ValidationError

from nfvcl_core.blueprints.blueprint_type_manager import day2_function
from nfvcl_core.providers.aggregator import ProvidersAggregator
from nfvcl_core.utils.blue_utils import get_class_path_str_from_obj, get_class_from_path
from nfvcl_core.utils.log import create_logger
from nfvcl_core.utils.metrics.grafana_utils import replace_all_datasources, update_queries_in_panels
from nfvcl_core_models.blueprints.blueprint import BlueprintNGState, BlueprintNGBaseModel, BlueprintNGException, RegisteredResource, MonitoringState, EnableMonitoringRequest, DisableMonitoringRequest, RestartVmRequest
from nfvcl_core_models.http_models import BlueprintNotFoundException, HttpRequestType
from nfvcl_core_models.monitoring.grafana_model import GrafanaFolderModel
from nfvcl_core_models.monitoring.monitoring import BlueprintMonitoringDefinition
from nfvcl_core_models.resources import Resource, ResourceConfiguration, ResourceDeployable, VmResource, \
    HelmChartResource

StateTypeVar = TypeVar("StateTypeVar")
CreateConfigTypeVar = TypeVar("CreateConfigTypeVar")


class BlueprintNG(Generic[StateTypeVar, CreateConfigTypeVar]):
    provider: ProvidersAggregator
    blueprint_type: str

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
        self.lock: threading.Lock = threading.Lock()

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
        # TODO also add a check for k8s resources
        if isinstance(resource, VmResource):
            resource_vm: VmResource = resource
            try:
                self.provider.topology_manager.get_vim_from_area_id_model(resource_vm.area)
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
        if self.base_model.monitoring_state:
            self.disable_monitoring(DisableMonitoringRequest(recursive=False))

        for children_id in self.base_model.children_blue_ids.copy():
            try:
                self.provider.delete_blueprint(children_id)
            except BlueprintNotFoundException:
                self.logger.warning(f"The children blueprint {children_id} has not been found. Could be deleted before, skipping...")
            self.deregister_children(children_id)

        # If the children blueprint was not registered in the parent, probably due to a crash in its creation
        for children in self.provider.blueprint_manager.get_blueprint_instances_by_parent_id(self.id):
            self.logger.warning(f"Deleting children blueprint that was not registered in the parent, probably due to a crash in its creation: {children.id}")
            try:
                # Here we shouldn't go through the provider, but directly to the blueprint_manager because the registration in the provider shouldn't have happened
                self.provider.blueprint_manager.delete_blueprint(children.id)
            except BlueprintNotFoundException:
                self.logger.warning(f"The children blueprint {children.id} has not been found. Could be deleted before, skipping...")

        for key, value in self.base_model.registered_resources.items():
            if isinstance(value.value, VmResource):
                self.provider.destroy_vm(value.value)
            elif isinstance(value.value, HelmChartResource):
                self.provider.uninstall_helm_chart(value.value)
            # TODO this is not implemented, currently the NetResource are destroyed by the provider in the final_cleanup
            # elif isinstance(value.value, NetResource):
            #     self.provider.destroy_net(value.value)
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
        try:
            for resource_id, resource in deserialized_dict["registered_resources"].items():
                if resource["value"]["type"] == "ResourceConfiguration":
                    instance.__override_variables_in_dict_ref(resource["value"], resource["value"], instance.base_model.registered_resources)
                    instance.register_resource(get_class_from_path(resource["type"]).model_validate(resource["value"]))
        except ValidationError as e:
            instance.logger.error(f"Unable to load state: {str(e)}")
            instance.base_model.corrupted = True
            instance.logger.error(f"Blueprint set as corrupted")

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

    def to_dict(self, detailed: bool, include_childrens: bool = False) -> dict:
        """
        Return a dictionary representation of the blueprint instance.

        Args:
            detailed: Return the same content saved in the database containing all the details of the blueprint.
            include_childrens: Recursively include the children blueprints dict.

        Returns:

        """
        if detailed:
            return self.serialize_base_model()
        else:
            dict_to_ret = {
                "id": self.base_model.id,
                "type": self.base_model.type,
                "status": self.base_model.status,
                "created": self.base_model.created,
                "protected": self.base_model.protected,
                "monitoring_enabled": self.base_model.monitoring_state is not None,
            }
            if include_childrens:
                dict_to_ret["childrens"] = []
                for children_id in self.base_model.children_blue_ids:
                    try:
                        children_blueprint = self.provider.blueprint_manager.get_blueprint_instance(children_id)
                        dict_to_ret["childrens"].append(children_blueprint.to_dict(detailed=detailed, include_childrens=include_childrens))
                    except BlueprintNotFoundException:
                        self.logger.warning(f"The children blueprint {children_id} has not been found. Could be deleted before, skipping...")
            if self.base_model.corrupted:
                dict_to_ret["corrupted"] = True
            return dict_to_ret

    def blueprint_monitoring_definition(self) -> Optional[BlueprintMonitoringDefinition]:
        """
        Return the monitoring definition for this blueprint, if any.
        """
        return None

    @day2_function("/enable_monitoring", [HttpRequestType.PUT])
    def enable_monitoring(self, request: EnableMonitoringRequest) -> None:
        self.logger.info("Enabling monitoring on blueprint")

        prometheus_id = request.prometheus_id
        grafana_id = request.grafana_id

        if self.base_model.monitoring_state is not None:
            raise BlueprintNGException(f"Monitoring is already enabled for this blueprint on prometheus server: {self.base_model.monitoring_state.prometheus_server_id}")

        monitoring_definition = self.blueprint_monitoring_definition()
        if monitoring_definition is None:
            raise BlueprintNGException("No monitoring definition found for this blueprint, cannot enable monitoring")

        self.base_model.monitoring_state = MonitoringState(
            prometheus_server_id=prometheus_id,
            grafana_server_id=grafana_id
        )

        for prometheus_target in monitoring_definition.prometheus_targets:
            prometheus_target.labels["deployed_by"] = "nfvcl"
            prometheus_target.labels["blueprint"] = self.id
            prometheus_target.labels["blueprint_type"] = self.blueprint_type

            self.base_model.monitoring_state.prometheus_targets.append(prometheus_target)

            # Save del target in the blueprint state
            self.provider.topology_manager.add_prometheus_target(prometheus_id, prometheus_target)

        grafana_server = self.provider.topology_manager.get_grafana(grafana_id)

        if grafana_id:
            self.provider.topology_manager.add_grafana_folder(grafana_id, GrafanaFolderModel(name=f"{self.id} - {self.blueprint_type}", blueprint_id=self.id), parent_by_blue_id=self.base_model.parent_blue_id)

        # TODO maybe we should move this in the provider?
        from nfvcl_core.managers import get_monitoring_manager
        get_monitoring_manager().sync_prometheus_targets_to_server(prometheus_id)
        get_monitoring_manager().sync_grafana_folders_to_server(grafana_server.id)

        self.base_model.monitoring_state.grafana_folder_id = grafana_server.root_folder.find_folder_by_blueprint_id(self.id).uid

        if grafana_id:
            for grafana_dashboard in monitoring_definition.grafana_dashboards:
                with open(grafana_dashboard.path, 'r', encoding='utf-8') as f:
                    try:
                        dashboard = json.load(f)
                        if "id" in dashboard:
                            dashboard["id"] = None
                        if "uid" in dashboard:
                            dashboard["uid"] = None
                        replace_all_datasources(dashboard, get_monitoring_manager().get_grafana_datasource_uid(grafana_id, prometheus_id))
                        update_queries_in_panels(dashboard.get("panels", []), f'"blueprint" = "{self.id}"')
                        get_monitoring_manager().add_grafana_dashboard(grafana_id, dashboard, grafana_server.root_folder.find_folder_by_blueprint_id(self.id).uid)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding {grafana_dashboard.path}: {e}")

        self.to_db()

        if request.recursive:
            # If recursive is set, enable monitoring on all children blueprints
            for children_id in self.base_model.children_blue_ids:
                try:
                    self.provider.call_blueprint_function(children_id, "enable_monitoring", request)
                except BlueprintNGException:
                    self.logger.warning(f"Could not enable monitoring on children blueprint {children_id}, skipping...")

        self.logger.info("Enabled monitoring on blueprint")

    @day2_function("/disable_monitoring", [HttpRequestType.PUT])
    def disable_monitoring(self, request: DisableMonitoringRequest) -> None:
        self.logger.info("Disabling monitoring on blueprint")
        # Removing from prometheus scraping using the reference.
        if self.base_model.monitoring_state is not None:
            prometheus_server = self.provider.topology_manager.get_prometheus(self.base_model.monitoring_state.prometheus_server_id)
            try:
                self.logger.debug(f"Removing targets from prometheus server {prometheus_server.ip}")
                self.provider.topology_manager.delete_prometheus_targets(prometheus_server.id, self.base_model.monitoring_state.prometheus_targets)
            except ValueError as e:
                self.logger.error(f"Could not remove targets from prometheus server {prometheus_server.id}: {e}")
            from nfvcl_core.managers import get_monitoring_manager
            get_monitoring_manager().sync_prometheus_targets_to_server(prometheus_server.id)

            if self.base_model.monitoring_state.grafana_server_id and self.base_model.parent_blue_id is None:
                grafana_server = self.provider.topology_manager.delete_grafana_folder(self.base_model.monitoring_state.grafana_server_id, self.base_model.monitoring_state.grafana_folder_id)
                get_monitoring_manager().sync_grafana_folders_to_server(grafana_server.id)

            self.base_model.monitoring_state = None
            self.to_db()
        else:
            self.logger.warning("Monitoring is not enabled for this blueprint, nothing to disable, disabling for children...")

        if request.recursive:
            # If recursive is set, disable monitoring on all children blueprints
            for children_id in self.base_model.children_blue_ids:
                try:
                    self.provider.call_blueprint_function(children_id, "disable_monitoring", request)
                except BlueprintNGException:
                    self.logger.warning(f"Could not disable monitoring on children blueprint {children_id}, skipping...")

        self.logger.info("Disabled monitoring on blueprint")

    @day2_function("/reboot_vm", [HttpRequestType.PUT])
    def reboot_vm(self, restart_vm_request: RestartVmRequest) -> None:
        """
        Reboot a VM by name
        Args:
            restart_vm_request: The name of the VM to be rebooted and optionally if the reboot should be hard (forceful)
        """
        self.logger.info(f"Rebooting VM {restart_vm_request.vm_name} in blueprint {self.id}")
        # Search the vm in the registered resources
        vm_resource: Optional[VmResource] = None
        for resource in self.base_model.registered_resources.values():
            if isinstance(resource.value, VmResource) and resource.value.name == restart_vm_request.vm_name:
                vm_resource = resource.value
                break
        if vm_resource:
            self.provider.reboot_vm(vm_resource, hard=restart_vm_request.hard)
        else:
            raise BlueprintNGException(f"VM {restart_vm_request.vm_name} not found in blueprint {self.id}")

        self.logger.info(f"Rebooted VM {restart_vm_request.vm_name} in blueprint {self.id}")
