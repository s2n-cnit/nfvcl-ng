from __future__ import annotations

import importlib
from typing import Any, List, Callable, Optional

from verboselogs import VerboseLogger

from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.lcm.blueprint_worker import BlueprintWorker
from nfvcl.blueprints_ng.lcm.performance_manager import get_performance_manager
from nfvcl.blueprints_ng.resources import VmResource
from nfvcl.models.blueprint_ng.worker_message import WorkerMessageType
from nfvcl.models.http_models import BlueprintNotFoundException, BlueprintAlreadyExisting, BlueprintProtectedException
from nfvcl.utils.database import get_ng_blue_by_id_filter, get_ng_blue_list
from nfvcl.utils.log import create_logger
from nfvcl.utils.util import generate_blueprint_id

BLUEPRINTS_MODULE_FOLDER: str = "nfvcl.blueprints_ng.modules"
logger: VerboseLogger = create_logger("BlueprintNGManager")

__blueprint_manager: BlueprintManager | None = None


def get_blueprint_manager() -> BlueprintManager:
    """
    Allow to retrieve the BlueprintManager (that can have only one instance)
    Returns:
        The blueprint manager
    """
    global __blueprint_manager
    if __blueprint_manager is not None:
        return __blueprint_manager
    else:
        __blueprint_manager = BlueprintManager()
        return __blueprint_manager


class BlueprintManager:
    """
    This class is responsible for managing blueprints.
    This class will manage all blueprints that have been created.
    When a request arrives at the NFVCL, the blueprint worker of the blueprint is returned.

    Attributes:
        worker_collection (dict[str, BlueprintWorker]): The collection of active workers
    """
    worker_collection: dict[str, BlueprintWorker] = {}

    def __init__(self):
        # Load the modules into the memory
        self._load_modules()

    def get_worker(self, blueprint_id: str) -> BlueprintWorker:
        """
        Return the blueprint dedicated worker, given the blueprint ID
        Args:
            blueprint_id: The ID of the blueprint

        Returns:
            The worker

        Raises:
            BlueprintNotFoundException if blue does nor exist.
        """
        if blueprint_id in self.worker_collection:
            # The worker for the blueprint has already been instantiated/re-instantiated
            return self.worker_collection[blueprint_id]
        else:
            blueprint = self._load_blue_from_db(blueprint_id)
            if blueprint is not None:
                worker = BlueprintWorker(blueprint)
                worker.start_listening()
                self.worker_collection[blueprint_id] = worker
                return worker
            else:
                logger.error(f"Blueprint {blueprint_id} not found")
                raise BlueprintNotFoundException(blueprint_id)

    def _load_blue_from_db(self, blueprint_id: str) -> BlueprintNG | None:
        """
        Load the blueprint (OBJ) from the database
        Args:
            blueprint_id: The ID of the blueprint to be loaded.

        Returns:
            The blueprint if found, None otherwise.
        """
        blue: dict = get_ng_blue_by_id_filter(blueprint_id)

        if blue is not None:
            blueprint = BlueprintNG.from_db(blue)
            return blueprint
        else:
            return None

    def _load_all_blue_dict_from_db(self, blueprint_type: str = None) -> List[dict]:
        """
        Load all the blueprints (dict) from the database
        Args:
            blueprint_type (Optional[str]): The type of the blueprint to be retrieved

        Returns:
            The blueprint (dict) list.
        """
        return get_ng_blue_list(blueprint_type)

    def _load_all_blue_from_db(self, blueprint_type: str = None, provider_initialization: bool = True) -> List[BlueprintNG]:
        """
        Load all the blueprints (ojb) from the database
        Args:
            blueprint_type (Optional[str]): The type of the blueprint to be retrieved
            provider_initialization (bool=True): If providers have to be initialized. If false -> blueprint cannot be used, it is just a reference from db.

        Returns:
            The blueprint list (List[BlueprintNG]).
        """
        blue_list = []
        for item in self._load_all_blue_dict_from_db(blueprint_type):
            logger.debug(f"Deserializing Blueprint {item['id']}")
            if provider_initialization:
                blue_list.append(BlueprintNG.from_db(item))
            else:
                blue_list.append(BlueprintNG.from_db_no_prov_init(item))
        return blue_list


    def create_blueprint(self, msg: Any, path: str, wait: bool = False, parent_id: str | None = None, callback: Optional[Callable] = None) -> str:
        """
        Create a base, EMPTY, blueprint given the type of the blueprint.
        Then create a dedicated worker for the blueprint that spawns (ASYNC) the blueprint on the VIM.
        Args:
            msg: The message received from the user. The type change on the blueprint type. It is checked by fastAPI on the request.
            path: The blueprint-specific path, the last part of the URL for the creation request (e.g., /nfvcl/v2/api/blue/vyos ----> path='vyos')
            wait: True to wait for blueprint creation, False otherwise
            parent_id: ID of the parent blueprint
            callback: Function to be called when the blueprint is created.

        Returns:
            The ID of the created blueprint.
        """
        blue_id = generate_blueprint_id()
        # Check that a blueprint with that ID is not existing in the DB
        if self._load_blue_from_db(blue_id) is not None:
            raise BlueprintAlreadyExisting(blue_id)
        else:
            # Get the class, based on the blue type.
            BlueClass = blueprint_type.get_blueprint_class(path)
            # Instantiate the object (creation of services is done by the worker)
            created_blue: BlueprintNG = BlueClass(blue_id)
            created_blue.base_model.parent_blue_id = parent_id
            # Saving the new blueprint to db
            created_blue.to_db()
            # Creating and starting the worker
            worker = BlueprintWorker(created_blue)
            worker.start_listening()  # Start another THREAD

            get_performance_manager().add_blueprint(blue_id, path)

            self.worker_collection[blue_id] = worker
            # Putting the creation message into the worker (the spawn happens asynch)
            if wait:
                worker.put_message_sync(WorkerMessageType.DAY0, f'{path}', msg)
            else:
                worker.put_message(WorkerMessageType.DAY0, f'{path}', msg, callback=callback)
            return blue_id

    def delete_blueprint(self, blueprint_id: str, wait: bool = False) -> str:
        """
        Deletes the blueprint from the NFVCL (DB+worker) if the blueprint is not protected.

        Args:
            blueprint_id: The ID of the blueprint to be deleted.
            wait: Wait for deletion to be complete

        Raises:
            BlueprintNotFoundException if blue does nor exist.
        """
        worker = self.get_worker(blueprint_id)
        if worker.blueprint.base_model.protected:
            raise BlueprintProtectedException(blueprint_id)

        if wait:
            worker.destroy_blueprint_sync()
        else:
            worker.destroy_blueprint()
        self.worker_collection.pop(blueprint_id)
        return blueprint_id

    def delete_all_blueprints(self) -> None:
        """
        Deletes all blueprints in the NFVCL (DB+worker).
        """
        blue_list: List[dict] = self._load_all_blue_dict_from_db()

        for blue in blue_list:
            try:
                self.delete_blueprint(blueprint_id=blue['id'])
            except BlueprintProtectedException:
                logger.warning(f"The deletion of blueprint {blue['id']} has been skipped cause it is protected")

    def get_blueprint_summary_by_id(self, blueprint_id: str, detailed: bool = False) -> dict:
        """
        Retrieves the blueprint summary for the given blueprint ID. If the blueprint is present in memory, returns it from there instead of DB.
        Args:
            blueprint_id: The blueprint to be retrieved.
            detailed: If true, return all the info saved in the database about the blueprints.

        Returns:
            The summary/details of a blueprint
        """
        return self.get_blueprint_instance_by_id(blueprint_id).to_dict(detailed)

    def get_blueprint_instance_by_id(self, blueprint_id: str) -> BlueprintNG:
        """
        Retrieves the blueprint summary for the given blueprint ID. If the blueprint is present in memory, returns it from there instead of DB.
        Args:
            blueprint_id: The blueprint to be retrieved.

        Returns:
            The summary/details of a blueprint
        """
        # If the blueprint is active and loaded in memory, then use the one in memory
        if blueprint_id in self.worker_collection:
            blueprint: BlueprintNG = self.worker_collection[blueprint_id].blueprint
        else:
            # Otherwise load it from the database
            blueprint: BlueprintNG = self._load_blue_from_db(blueprint_id)
        if blueprint is None:
            raise BlueprintNotFoundException(blueprint_id)
        return blueprint

    def get_blueprint_summary_list(self, blue_type: str, detailed: bool = False) -> List[dict]:
        """
        Retrieves the blueprint summary for all the blueprints. If a blueprint is present in memory, return it from there instead of DB.
        Args:
            blue_type: The optional filter to be used to filter results on a type basis (e.g., 'vyos').
            detailed: If true, return all the info saved in the database about the blueprints.

        Returns:
            The summary/details of all blueprints that satisfy the given filter.
        """
        blue_list = self._load_all_blue_from_db(blue_type, provider_initialization=False)
        blue_mem_id_list = self.worker_collection.keys()
        # Replace blueprints from DB with the ones that are present in the memory.
        for i in range(len(blue_list)):
            if blue_list[i].id in blue_mem_id_list:
                blue_list[i] = self.worker_collection[blue_list[i].id].blueprint

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
            The
        """
        blue_list: List[BlueprintNG] = self._load_all_blue_from_db()
        for blue in blue_list:
            registered_vms = blue.get_registered_resources(type_filter="nfvcl.blueprints_ng.resources.VmResource")  # Getting only VMs
            for registered_resource in registered_vms:
                vm: VmResource
                vm = registered_resource.value
                if ipv4 == vm.access_ip:
                    return vm
        return None

    def _load_modules(self):
        """
        IMPORT all blueprints modules in the NFVCL. When a module is loaded in the memory, decorators are read and executed.
        @blueprint_type is used to actually load the info about every module
        """
        importlib.import_module(BLUEPRINTS_MODULE_FOLDER)
