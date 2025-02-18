from __future__ import annotations

import importlib
from typing import Any, List, Optional, Dict, Callable, TYPE_CHECKING

from nfvcl_core.database import BlueprintRepository
from nfvcl_core.managers import GenericManager, EventManager
from nfvcl_core_models.event_types import BlueEventType, NFVCLEventTopics
from nfvcl_core_models.performance import BlueprintPerformanceType
from nfvcl_core_models.pre_work import PreWorkCallbackResponse, run_pre_work_callback

if TYPE_CHECKING:
    from nfvcl_core.managers import TopologyManager, PDUManager, PerformanceManager
from nfvcl_core.blueprints import BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.blueprints.blueprint import BlueprintNGStatus
from nfvcl_core_models.resources import VmResource
from nfvcl_core_models.http_models import BlueprintAlreadyExisting, BlueprintProtectedException
from nfvcl_core_models.response_model import OssCompliantResponse, OssStatus
from nfvcl_core.providers.aggregator import ProvidersAggregator
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

    def __init__(self, blueprint_repository: BlueprintRepository, topology_manager: TopologyManager, pdu_manager: PDUManager, performance_manager: PerformanceManager, event_manager: EventManager):
        super().__init__()
        self._blueprint_repository = blueprint_repository
        self._topology_manager = topology_manager
        self._pdu_manager = pdu_manager
        self._performance_manager = performance_manager
        self._event_manager = event_manager

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
            blueprint_instance = BlueprintNG.from_db(item, provider=ProvidersAggregator(topology_manager=self._topology_manager, blueprint_manager=self, pdu_manager=self._pdu_manager, performance_manager=self._performance_manager))
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
                created_blue.provider = ProvidersAggregator(created_blue, topology_manager=self._topology_manager, blueprint_manager=self, pdu_manager=self._pdu_manager, performance_manager=self._performance_manager)
                created_blue.base_model.parent_blue_id = parent_id
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
                    raise e
                self.set_blueprint_status(blue_id, BlueprintNGStatus.idle())
                self._performance_manager.end_operation(performance_operation_id)

                self._event_manager.fire_event(NFVCLEventTopics.BLUEPRINT_TOPIC, BlueEventType.BLUE_CREATED, data=created_blue.base_model)
            return blue_id

    def update_blueprint(self, blueprint_id: str, path: str, msg: Any, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> Any:
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
        run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.processing, detail=f"Blueprint day2 message for {blueprint_id} given to the worker..."))

        function = blueprint_type.get_function_to_be_called(path)
        blueprint = self.get_blueprint_instance(blueprint_id)

        if blueprint is None:
            run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.failed, detail=f"Blueprint {blueprint_id} not found"))
            raise Exception(f"Blueprint {blueprint_id} not found")

        with blueprint.lock:
            self.set_blueprint_status(blueprint.id, BlueprintNGStatus.running_day2())

            performance_operation_id = self._performance_manager.start_operation(blueprint_id, BlueprintPerformanceType.DAY2, path.split("/")[-1])
            try:
                if msg:
                    result = getattr(blueprint, function.__name__)(msg)
                else:
                    result = getattr(blueprint, function.__name__)()
            except Exception as e:
                self.logger.error(f"Error during the update of blueprint {blueprint_id}. Error: {e}")
                self.set_blueprint_status(blueprint.id, BlueprintNGStatus.error_state(str(e)))
                raise e
            self._performance_manager.end_operation(performance_operation_id)

            self.set_blueprint_status(blueprint.id, BlueprintNGStatus.idle())
        return result

    def get_from_blueprint(self, blueprint_id: str, path: str) -> Any:
        """
        Get data from the blueprint with the given ID
        Args:
            blueprint_id: The ID of the blueprint from which the data will be retrieved
            path: The blueprint-specific path, the last part of the URL for the creation request (e.g., /nfvcl/v2/api/blue/vyos ----> path='vyos')
        """
        blueprint = self.get_blueprint_instance(blueprint_id)
        function = blueprint_type.get_function_to_be_called(path)

        if blueprint.lock.locked():
            raise Exception(f"Blueprint {blueprint_id} is locked, since this request is synchronous, it is not possible to get data from a locked blueprint")

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
            result = getattr(blueprint, function_name)(*args, **kwargs)
            self._performance_manager.end_operation(performance_operation_id)
        return result

    def delete_blueprint(self, blueprint_id: str, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> str:
        """
        Deletes the blueprint from the NFVCL if the blueprint is not protected.

        Args:
            blueprint_id: The ID of the blueprint to be deleted.
            pre_work_callback: Callback that is called before the creation of the blueprint.

        Raises:
            BlueprintNotFoundException if blue does nor exist.
        """
        run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.processing, detail=f"Blueprint deletion message for {blueprint_id} given to the worker..."))

        blueprint_instance = self.get_blueprint_instance(blueprint_id)

        if blueprint_instance is None:
            run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.failed, detail=f"Blueprint {blueprint_id} not found"))
            raise Exception(f"Blueprint {blueprint_id} not found")

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
                self.logger.error(f"Error during deletion of blueprint {blueprint_id}. Error: {e}")
                self.set_blueprint_status(blueprint_id, BlueprintNGStatus.error_state(str(e)))
                raise e
            self._performance_manager.end_operation(performance_operation_id)

        return blueprint_id

    def delete_all_blueprints(self, pre_work_callback: Optional[Callable[[PreWorkCallbackResponse], None]] = None) -> None:
        """
        Deletes all blueprints in the NFVCL.
        """
        run_pre_work_callback(pre_work_callback, OssCompliantResponse(status=OssStatus.processing, detail=f"Blueprints are being deleted..."))

        blueprints = list(self.blueprint_dict.keys())
        for blue_id in blueprints:
            try:
                self.delete_blueprint(blue_id)
            except BlueprintProtectedException:
                self.logger.warning(f"The deletion of blueprint {blue_id} has been skipped cause it is protected")

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
        return self.get_blueprint_instance(blueprint_id).to_dict(detailed)

    def get_blueprint_summary_list(self, blue_type: str, detailed: bool = False) -> List[dict]:
        """
        Retrieves the blueprint summary for all the blueprints. If a blueprint is present in memory, return it from there instead of DB.
        Args:
            blue_type: The optional filter to be used to filter results on a type basis (e.g., 'vyos').
            detailed: If true, return all the info saved in the database about the blueprints.

        Returns:
            The summary/details of all blueprints that satisfy the given filter.
        """
        blue_list = self.get_blueprint_instances(blue_type)

        if detailed:
            return [blueprint.to_dict(detailed=True) for blueprint in blue_list]
        else:
            return [blueprint.to_dict(detailed=False) for blueprint in blue_list]

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
            registered_vms = blue.get_registered_resources(type_filter="nfvcl_core.models.resources.VmResource")  # Getting only VMs
            for registered_resource in registered_vms:
                vm: VmResource
                vm = registered_resource.value
                if ipv4 == vm.access_ip:
                    return vm
        return None

    def set_blueprint_status(self, blueprint_id: str, status: BlueprintNGStatus) -> None:
        """
        Set the status of the blueprint with the given ID
        Args:
            blueprint_id: The ID of the blueprint to be updated
            status: The status to be set
        """
        # TODO fire event
        blueprint = self.get_blueprint_instance(blueprint_id)
        blueprint.base_model.status = status
        blueprint.to_db()
