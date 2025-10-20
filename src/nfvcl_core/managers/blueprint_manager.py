from __future__ import annotations

import importlib
from typing import Any, List, Optional, Dict, Callable, TYPE_CHECKING

from keystoneauth1.exceptions import Unauthorized

from nfvcl_core.database.blueprint_repository import BlueprintRepository
from nfvcl_core.database.provider_repository import ProviderDataRepository
from nfvcl_core.database.snapshot_repository import SnapshotRepository
from nfvcl_core.managers import GenericManager, EventManager
from nfvcl_core.utils.blue_utils import get_class_path_str_from_obj, get_class_from_path
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.blueprints.blueprint import BlueprintNGBaseModel
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.event_types import BlueEventType, NFVCLEventTopics
from nfvcl_core_models.performance import BlueprintPerformanceType
from nfvcl_core_models.pre_work import PreWorkCallbackResponse, run_pre_work_callback
from nfvcl_core_models.providers.providers import ProviderDataAggregate

if TYPE_CHECKING:
    from nfvcl_core.managers import TopologyManager, PDUManager, PerformanceManager, VimClientsManager
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.blueprints.blueprint import BlueprintNGStatus, RegisteredBlueprintCall, FunctionType
from nfvcl_core_models.resources import VmResource
from nfvcl_core_models.http_models import BlueprintAlreadyExisting, BlueprintProtectedException
from nfvcl_core_models.response_model import OssCompliantResponse, OssStatus
from nfvcl_core.blueprints.provider_aggregator import ProvidersAggregator
from nfvcl_core.utils.util import generate_blueprint_id

BLUEPRINTS_MODULE_FOLDER: str = "nfvcl.blueprints_ng.modules"


class BlueprintManager(GenericManager):
    """
    This class is responsible for managing blueprints.
    This class will manage all blueprints that have been created.

    Attributes:
        blueprint_dict (Dict[str, BlueprintNG]): The dictionary that contains all the blueprints instances.
    """
    blueprint_dict: Dict[str, BlueprintNG] = {}

    def __init__(self, blueprint_repository: BlueprintRepository, provider_repository: ProviderDataRepository, snapshot_repository: SnapshotRepository, topology_manager: TopologyManager, pdu_manager: PDUManager, performance_manager: PerformanceManager, event_manager: EventManager, vim_clients_manager: VimClientsManager):
        super().__init__()
        self._blueprint_repository = blueprint_repository
        self._provider_repository = provider_repository
        self._snapshot_repository = snapshot_repository
        self._topology_manager = topology_manager
        self._pdu_manager = pdu_manager
        self._performance_manager = performance_manager
        self._event_manager = event_manager
        self._vim_clients_manager = vim_clients_manager

    def load(self):
        """
        Load blueprints modules and instances from the database
        """
        self.logger.info("Loading Blueprint Modules")
        self._load_modules()
        self.logger.info("Loading Blueprint Modules Completed")
        self.logger.info("Loading Blueprint Instances")
        self._load_all_blueprint_instances_from_db()
        self.logger.info("Loading Blueprint Instances Completed")

    def save_blueprint(self, blueprint: BlueprintNG) -> None:
        """
        Save the blueprint to the manager
        Args:
            blueprint: The blueprint to be saved
        """
        self.blueprint_dict[blueprint.id] = blueprint
        self._blueprint_repository.save_blueprint(blueprint.base_model)
        self._provider_repository.save_provider_data(blueprint.provider.get_provider_data_aggregate())

    def destroy_blueprint(self, blueprint: BlueprintNG) -> None:
        """
        Destroy the blueprint from the manager
        Args:
            blueprint: The blueprint to be destroyed
        """
        self.blueprint_dict.pop(blueprint.id)
        self._blueprint_repository.delete_blueprint(blueprint.id)

    def get_blueprint_instance(self, blueprint_id: str) -> Optional[BlueprintNG]:
        """
        Return the blueprint instance, given the blueprint ID
        Args:
            blueprint_id: The ID of the blueprint

        Returns:
            The blueprint instance
        """
        return self.blueprint_dict.get(blueprint_id, None)

    def get_blueprint_instances(self, blue_type: Optional[str] = None) -> List[BlueprintNG]:
        """
        Return the blueprint instances of the given type
        Args:
            blue_type: The type of the blueprints
        Returns:
            List of blueprint instances
        """
        if blue_type:
            return list(filter(lambda x: x.base_model.type == blue_type, self.blueprint_dict.values()))
        else:
            return list(self.blueprint_dict.values())

    def get_blueprint_instances_by_parent_id(self, parent_id: str) -> List[BlueprintNG]:
        """
        Return the blueprint instances that have the given parent ID
        Args:
            parent_id: The parent ID of the blueprint

        Returns:
            List of blueprint instances
        """
        return list(filter(lambda x: x.base_model.parent_blue_id == parent_id, self.blueprint_dict.values()))

    def _load_modules(self):
        """
        IMPORT all blueprints modules in the NFVCL. When a module is loaded in the memory, decorators are read and executed.
        @blueprint_type is used to actually load the info about every module
        """
        importlib.import_module(BLUEPRINTS_MODULE_FOLDER)

    def _load_all_blueprint_instances_from_db(self):
        """
        Load all the blueprints instances from the database
        """
        for item in self._blueprint_repository.get_all_dict():
            self.logger.debug(f"Loading Blueprint instance {item['id']}")
            blueprint_instance: BlueprintNG = BlueprintNG.from_db(item)

            provider_data_aggregate = self._provider_repository.find_by_blueprint_id(blueprint_instance.id)
            if provider_data_aggregate is None:
                provider_data_aggregate = ProviderDataAggregate(blueprint_id=blueprint_instance.id)

            provider = ProvidersAggregator(
                blueprint_id=blueprint_instance.id,
                persistence_function=blueprint_instance.to_db,
                topology_manager=self._topology_manager,
                blueprint_manager=self,
                pdu_manager=self._pdu_manager,
                performance_manager=self._performance_manager,
                vim_clients_manager=self._vim_clients_manager,
                provider_data_aggregate=provider_data_aggregate
            )
            blueprint_instance.provider = provider
            self.blueprint_dict[item['id']] = blueprint_instance

    def create_blueprint(self, path: str, msg: Any, parent_id: str | None = None, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> str:
        """
        Create a base, EMPTY, blueprint given the type of the blueprint.
        Then create a dedicated worker for the blueprint that spawns (ASYNC) the blueprint on the VIM.
        Args:
            msg: The message received from the user. The type change on the blueprint type. It is checked by fastAPI on the request.
            path: The blueprint-specific path, the last part of the URL for the creation request (e.g., /nfvcl/v2/api/blue/vyos ----> path='vyos')
            parent_id: ID of the parent blueprint
            pre_work_callback: Callback that is called before the creation of the blueprint.

        Returns:
            The ID of the created blueprint.
        """

        self._event_manager.fire_event(NFVCLEventTopics.BLUEPRINT_TOPIC, BlueEventType.BLUE_STARTED_DAY0, data={"path": path, "msg": msg})

        blue_id = generate_blueprint_id()

        # Check that a blueprint with that ID is not existing in the DB
        if self.get_blueprint_instance(blue_id) is not None:
            run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.failed, detail=f"Blueprint with ID {blue_id} already exist, retry..."))
            raise BlueprintAlreadyExisting(blue_id)
        else:
            run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.deploying, detail=f"Blueprint {blue_id} is being deployed..."))

            # Get the class, based on the blue type.
            BlueClass = blueprint_type.get_blueprint_class(path)
            # Instantiate the object (creation of services is done by the worker)
            created_blue: BlueprintNG = BlueClass(blue_id)
            with created_blue.lock:
                created_blue.provider = ProvidersAggregator(blueprint_id=created_blue.id, persistence_function=created_blue.to_db, topology_manager=self._topology_manager, blueprint_manager=self, pdu_manager=self._pdu_manager, performance_manager=self._performance_manager, vim_clients_manager=self._vim_clients_manager)
                created_blue.base_model.parent_blue_id = parent_id
                if isinstance(msg, NFVCLBaseModel):
                    created_blue.base_model.day_2_call_history.append(RegisteredBlueprintCall(function_name=path, msg=msg.model_dump(), msg_type=get_class_path_str_from_obj(msg), function_type=FunctionType.DAY0))
                else:
                    created_blue.base_model.day_2_call_history.append(RegisteredBlueprintCall(function_name=path, msg={"msg": f"{msg}"}, function_type=FunctionType.DAY0))
                # Saving the new blueprint to db
                created_blue.to_db()
                self.blueprint_dict[blue_id] = created_blue

                self.set_blueprint_status(blue_id, BlueprintNGStatus.deploying(created_blue.id))

                self._performance_manager.add_blueprint(created_blue.id, path)

                performance_operation_id = self._performance_manager.start_operation(created_blue.id, BlueprintPerformanceType.DAY0, "create")
                try:
                    created_blue.create(msg)
                except Exception as e:
                    self.logger.error(f"Error during the creation of blueprint {blue_id}. Error: {e}")
                    self.set_blueprint_status(blue_id, BlueprintNGStatus.error_state(str(e)))
                    self._performance_manager.set_error(blue_id, True)
                    raise e
                self.set_blueprint_status(blue_id, BlueprintNGStatus.idle())
                self._performance_manager.end_operation(performance_operation_id)

                self._event_manager.fire_event(NFVCLEventTopics.BLUEPRINT_TOPIC, BlueEventType.BLUE_CREATED, data=created_blue.base_model)
                self.logger.success(f"Blueprint {blue_id} created successfully")
            return blue_id

    def update_blueprint(self, blueprint_id: str, path: str, msg: Any = None, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> Any:
        """
        Update the blueprint with the given ID
        Args:
            blueprint_id: The ID of the blueprint to be updated
            path: The blueprint-specific path, the last part of the URL for the creation request (e.g., /nfvcl/v2/api/blue/vyos ----> path='vyos')
            msg: The message received from the user. The type change on the blueprint type. It is checked by fastAPI on the request.
            pre_work_callback: Callback that is called before the creation of the blueprint.

        Returns:
            The ID of the updated blueprint.
        """
        b_type = path.split("/")[0]
        blueprint_module = blueprint_type.get_blueprint_module(b_type)

        function = blueprint_type.get_function_to_be_called(path)
        blueprint = self.get_blueprint_instance(blueprint_id)

        if blueprint is None:
            run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.failed, detail=f"Blueprint {blueprint_id} not found"))
            raise NFVCLCoreException(f"Blueprint {blueprint_id} not found")

        if get_class_path_str_from_obj(blueprint) != f"{blueprint_module.module}.{blueprint_module.class_name}":
            run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.failed, detail=f"Blueprint {blueprint_id} is not of the type {b_type}"))
            raise NFVCLCoreException(f"Blueprint {blueprint_id} is not of the type {b_type}")

        run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.processing, detail=f"Blueprint day2 message for {blueprint_id} given to the worker..."))

        with blueprint.lock:
            self.set_blueprint_status(blueprint.id, BlueprintNGStatus.running_day2())

            performance_operation_id = self._performance_manager.start_operation(blueprint_id, BlueprintPerformanceType.DAY2, path.split("/")[-1])
            try:
                if msg:
                    if isinstance(msg, NFVCLBaseModel):
                        blueprint.base_model.day_2_call_history.append(RegisteredBlueprintCall(function_name=path, msg=msg.model_dump(), msg_type=get_class_path_str_from_obj(msg), function_type=FunctionType.DAY2))
                    else:
                        blueprint.base_model.day_2_call_history.append(RegisteredBlueprintCall(function_name=path, msg={"msg": f"{msg}"}, function_type=FunctionType.DAY2))
                    result = getattr(blueprint, function.__name__)(msg)
                else:
                    result = getattr(blueprint, function.__name__)()
            except Exception as e:
                self.logger.error(f"Error during the update of blueprint {blueprint_id}. Error: {e}")
                self.set_blueprint_status(blueprint.id, BlueprintNGStatus.error_state(str(e)))
                self._performance_manager.set_error(blueprint.id, True)
                raise e
            self._performance_manager.end_operation(performance_operation_id)

            self.set_blueprint_status(blueprint.id, BlueprintNGStatus.idle())
            # EVENT FIRE
            self._event_manager.fire_event(NFVCLEventTopics.BLUEPRINT_TOPIC, BlueEventType.BLUE_UPDATED, data=blueprint.base_model)
        return result

    def get_from_blueprint(self, blueprint_id: str, path: str) -> Any:
        """
        Get data from the blueprint with the given ID
        Args:
            blueprint_id: The ID of the blueprint from which the data will be retrieved
            path: The blueprint-specific path, the last part of the URL for the creation request (e.g., /nfvcl/v2/api/blue/vyos ----> path='vyos')
        """
        blueprint = self.get_blueprint_instance(blueprint_id)
        if blueprint is None:
            raise NFVCLCoreException(f"Blueprint {blueprint_id} does not exist", http_equivalent_code=404)
        function = blueprint_type.get_function_to_be_called(path)

        if blueprint.lock.locked():
            raise NFVCLCoreException(f"Blueprint {blueprint_id} is locked, since this request is synchronous, it is not possible to get data from a locked blueprint")

        with blueprint.lock:
            try:
                result = getattr(blueprint, function.__name__)()
            except Exception as e:
                self.logger.error(f"Error during the get DAY2 on blueprint {blueprint_id}. Error: {e}")
                self.set_blueprint_status(blueprint.id, BlueprintNGStatus.error_state(str(e)))
                raise e

        return result

    def call_function(self, blueprint_id: str, function_name: str, *args, **kwargs) -> Any:
        """
        Call a function on the blueprint with the given ID
        Args:
            blueprint_id: Id of the blueprint to call the function on
            function_name: Name of the function to be called
            *args: Arguments of the called function
            **kwargs: Keyword arguments of the called function

        Returns: Return of the called function
        """

        blueprint = self.get_blueprint_instance(blueprint_id)
        with blueprint.lock:
            # BlueprintOperationCallbackModel
            performance_operation_id = self._performance_manager.start_operation(blueprint_id, BlueprintPerformanceType.CROSS_BLUEPRINT_FUNCTION_CALL, function_name)
            call_msg = RegisteredBlueprintCall(function_name=function_name, extra={"args": f"{args}", "kwargs": f"{kwargs}"})
            blueprint.base_model.day_2_call_history.append(call_msg)
            result = getattr(blueprint, function_name)(*args, **kwargs)
            self._performance_manager.end_operation(performance_operation_id)
        return result

    def delete_blueprint(self, blueprint_id: str, force_deletion: Optional[bool] = False, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> str:
        """
        Deletes the blueprint from the NFVCL if the blueprint is not protected.

        Args:
            blueprint_id: The ID of the blueprint to be deleted.
            pre_work_callback: Callback that is called before the creation of the blueprint.
            force_deletion: Force deletion without ensuring that resources are deleted from remote VIMs or K8S Clusters

        Raises:
            BlueprintNotFoundException if blue does nor exist.
        """
        blueprint_instance = self.get_blueprint_instance(blueprint_id)

        if blueprint_instance is None:
            run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.failed, detail=f"Blueprint {blueprint_id} not found"))
            raise NFVCLCoreException(f"Blueprint {blueprint_id} not found")

        run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.processing, detail=f"Blueprint deletion message for {blueprint_id} given to the worker..."))

        with blueprint_instance.lock:
            performance_operation_id = self._performance_manager.start_operation(blueprint_id, BlueprintPerformanceType.DELETION, "delete")
            try:
                if blueprint_instance.base_model.protected:
                    raise BlueprintProtectedException(blueprint_id)

                self.set_blueprint_status(blueprint_id, BlueprintNGStatus.destroying(blueprint_id))
                blueprint_instance.destroy()
                self.blueprint_dict.pop(blueprint_id)
                self._blueprint_repository.delete_blueprint(blueprint_id)
            except Exception as e:
                if force_deletion:
                    self.logger.warning("Force deletion is enabled! Blue will be destroyed without ensuring that resources are deleted from remote VIMs or K8S Clusters")
                    self.logger.error(f"Error during deletion of blueprint {blueprint_id}. Error: {e}")
                    self.blueprint_dict.pop(blueprint_id)
                    self._blueprint_repository.delete_blueprint(blueprint_id)
                else:
                    self.logger.error(f"Error during deletion of blueprint {blueprint_id}. Error: {e}")
                    self.set_blueprint_status(blueprint_id, BlueprintNGStatus.error_state(str(e)))
                    self._performance_manager.set_error(blueprint_id, True)
                    raise e
            self._performance_manager.end_operation(performance_operation_id)
            self.logger.success(f"Blueprint {blueprint_id} deleted successfully")

        return blueprint_id

    def delete_all_blueprints(self, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> None:
        """
        Deletes all blueprints in the NFVCL.
        """
        run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.processing, detail="Blueprints are being deleted..."))

        blueprints = list(self.blueprint_dict.keys())
        for blue_id in blueprints:
            try:
                self.delete_blueprint(blue_id)
            except BlueprintProtectedException:
                self.logger.warning(f"The deletion of blueprint {blue_id} has been skipped cause it is protected")
            except Unauthorized: # CLient Openstack crash
                self.logger.warning(f"The deletion of blueprint {blue_id} has been skipped cause Openstack Client Failed")

    def protect_blueprint(self, blueprint_id: str, protect: bool) -> dict:
        """
        Protects or unprotects the blueprint with the given ID
        Args:
            blueprint_id: The ID of the blueprint to be protected
            protect: If true, protect the blueprint
        """
        blueprint = self.get_blueprint_instance(blueprint_id)
        blueprint.base_model.protected = protect
        blueprint.to_db()
        return self.get_blueprint_summary_by_id(blueprint_id, detailed=False)

    def get_blueprint_summary_by_id(self, blueprint_id: str, detailed: bool = False) -> dict:
        """
        Retrieves the blueprint summary for the given blueprint ID. If the blueprint is present in memory, returns it from there instead of DB.
        Args:
            blueprint_id: The blueprint to be retrieved.
            detailed: If true, return all the info saved in the database about the blueprints.

        Returns:
            The summary/details of a blueprint
        """
        blue = self.get_blueprint_instance(blueprint_id)
        if blue is None:
            raise NFVCLCoreException(f"Blueprint {blueprint_id} not found")
        return blue.to_dict(detailed)

    def get_blueprint_summary_list(self, blue_type: str, detailed: bool = False, tree: bool = False) -> List[dict]:
        """
        Retrieves the blueprint summary for all the blueprints. If a blueprint is present in memory, return it from there instead of DB.
        Args:
            blue_type: The optional filter to be used to filter results on a type basis (e.g., 'vyos').
            detailed: If true, return all the info saved in the database about the blueprints.
            tree: If true, return the tree structure of the blueprints.

        Returns:
            The summary/details of all blueprints that satisfy the given filter.
        """
        blue_list = self.get_blueprint_instances(blue_type)
        if tree:
            list_to_ret = []
            for parent in filter(lambda x: x.base_model.parent_blue_id is None, blue_list):
                list_to_ret.append(parent.to_dict(detailed=detailed, include_childrens=True))
            return list_to_ret
        else:
            return [blueprint.to_dict(detailed=detailed) for blueprint in blue_list]

    def get_vm_target_by_ip(self, ipv4: str) -> VmResource | None:
        """
        Check if there is a VM, belonging to any Blueprint, that have the required IP as interface
        This method was required to execute Playbooks into VMs required by project Horse.
        Args:
            ipv4: The IPv4 to be used for searching the VM

        Returns:
            The VM that has the IP, None otherwise
        """
        for blue in self.blueprint_dict.values():
            # TODO the type here need to be dynamic
            registered_vms = blue.get_registered_resources(type_filter="nfvcl_core_models.resources.VmResource")  # Getting only VMs
            for registered_resource in registered_vms:
                vm: VmResource
                vm = registered_resource.value
                if ipv4 == vm.access_ip:
                    return vm
        return None

    def get_snapshot_list(self) -> List[BlueprintNGBaseModel]:
        """
        Get the list of all the snapshots
        Returns:
            the list of all the snapshots

        Notes:
            SYNC
        """
        return self._snapshot_repository.get_all()

    def get_snapshot(self, snapshot_name: str) -> BlueprintNGBaseModel:
        """
        Get a specific snapshots
        Returns:
            the snapshot if found

        Raises:
            NFVCLCoreException: If the snapshot is not found

        Notes:
            SYNC
        """
        snapshot = self._snapshot_repository.find_one_safe({'id': snapshot_name})
        if snapshot is None:
            raise NFVCLCoreException(f"Snapshot {snapshot_name} not found")
        return snapshot

    def snapshot_blueprint(self, snapshot_name: str, blueprint_id: str, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> BlueprintNGBaseModel:
        """
        Snapshot the blueprint with the given ID
        Args:
            blueprint_id: The ID of the blueprint to be snapshotted
            snapshot_name: The name of the snapshot

        Raises:
            NFVCLCoreException: If the blueprint is not found or if the blueprint is not in idle state

        Notes:
            SYNC
        """
        blueprint = self.get_blueprint_instance(blueprint_id)
        if blueprint is None:
            raise NFVCLCoreException(f"Blueprint {blueprint_id} not found")
        if not blueprint.base_model.status.is_idle():
            raise NFVCLCoreException(f"Blueprint {blueprint_id} is not in idle state, cannot snapshot")
        snapshot = blueprint.base_model.get_snapshot(snapshot_name)
        self._snapshot_repository.save_snapshot(snapshot)
        return snapshot

    def snapshot_restore(self, snapshot_name: str, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> None:
        """
        Restore the blueprint from the snapshot with the given name
        Args:
            snapshot_name: The name of the snapshot
            pre_work_callback: Callback that is called before the creation of the blueprint.

        Raises:
            NFVCLCoreException: If the snapshot is not found or if the snapshot is corrupted

        Notes:
            ASYNC
        """
        snapshot = self._snapshot_repository.get_snapshot(snapshot_name)
        if snapshot is None:
            err_message = f"Snapshot {snapshot_name} not found"
            run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.failed, detail=err_message))
            raise NFVCLCoreException(err_message)
        # Looks for creation request in the blueprint
        creation_requests = [x for x in snapshot.day_2_call_history if x.function_type == FunctionType.DAY0.value]
        if len(creation_requests) != 1:
            err_message = f"Snapshot {snapshot_name} is corrupted, creation request must be 1, found {len(creation_requests)}"
            run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.failed, detail=err_message))
            raise NFVCLCoreException(err_message)
        # Start the creation of the blueprint
        run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.processing, detail=f"Snapshot {snapshot_name} is being restored..."))
        created_blueprint_id = self.create_blueprint(creation_requests[0].function_name, snapshot.create_config, parent_id=snapshot.parent_blue_id, pre_work_callback=pre_work_callback)
        # Reapplying every day2 call, they should be in order
        for day2_call in snapshot.day_2_call_history:
            if day2_call.function_type == FunctionType.DAY2.value:
                blue_class: NFVCLBaseModel = get_class_from_path(day2_call.msg_type)  # It is not strictly a NFVCLBaseModel, but it should be a model
                message_model = blue_class.model_validate(day2_call.msg)
                self.update_blueprint(created_blueprint_id, day2_call.function_name, message_model, pre_work_callback=pre_work_callback)

    def snapshot_and_delete(self, snapshot_name: str, blueprint_id: str, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> None:
        """
        Snapshot the blueprint with the given ID and then delete the blueprint
        Args:
            snapshot_name: The name of the snapshot to be created
            blueprint_id: The ID of the blueprint to be snapshotted and deleted
            pre_work_callback: Callback that is called before the creation of the blueprint.

        Notes:
            ASYNC
        """
        # NOTE: Async callback is the one inside the function delete_blueprint
        self.snapshot_blueprint(snapshot_name, blueprint_id, pre_work_callback=pre_work_callback)
        self.delete_blueprint(blueprint_id)

    def snapshot_delete(self, snapshot_name: str) -> BlueprintNGBaseModel:
        """
        Delete the snapshot with the given name
        Args:
            snapshot_name: The name of the snapshot to be deleted

        Returns:
            The deleted snapshot
        """
        snapshot = self.get_snapshot(snapshot_name)
        self._snapshot_repository.delete_snapshot(snapshot.id)
        return snapshot

    def set_blueprint_status(self, blueprint_id: str, status: BlueprintNGStatus) -> None:
        """
        Set the status of the blueprint with the given ID
        Args:
            blueprint_id: The ID of the blueprint to be updated
            status: The status to be set
        """
        blueprint = self.get_blueprint_instance(blueprint_id)
        blueprint.base_model.status = status
        blueprint.to_db()
        self._event_manager.fire_event(NFVCLEventTopics.BLUEPRINT_TOPIC, BlueEventType.BLUE_STATUS_CHANGED, data=blueprint.base_model)
