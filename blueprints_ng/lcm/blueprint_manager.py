import importlib
from logging import Logger
from typing import Callable, Any, List

from blueprints_ng.providers.blueprint_ng_provider_native import BlueprintsNgProviderNative
from fastapi import APIRouter
from blueprints_ng.blueprint_ng import BlueprintNG
from blueprints_ng.lcm.blueprint_type_manager import get_blueprint_class, get_registered_modules
from blueprints_ng.lcm.blueprint_worker import BlueprintWorker
from blueprints_ng.providers.blueprint_ng_provider_demo import BlueprintsNgProviderDemo
from models.blueprint_ng.worker_message import WorkerMessageType
from models.http_models import BlueprintNotFoundException, BlueprintAlreadyExisting
from utils.persistency import get_ng_blue_by_id_filter, get_ng_blue_list
from utils.log import create_logger
from utils.util import generate_blueprint_id

BLUEPRINTS_MODULE_FOLDER: str = "blueprints_ng.modules"
logger: Logger = create_logger("BlueprintNGManager")


class BlueprintManager:
    """
    This class is responsible for managing blueprints. This class will manage all blueprints that have been created.
    When a request arrives at the NFVCL, the blueprint worker of the blueprint is returned.

    Attributes:
        worker_collection (dict[str, BlueprintWorker]): The collection of active workers
        blue_router (APIRouter): The main router for the blueprints
        create_endpoint (Callable): The function to be pointed for ALL blueprints creation.
        update_endpoint (Callable): The function to be pointed for ALL blueprints day2 calls.
    """
    worker_collection: dict[str, BlueprintWorker] = {}
    blue_router: APIRouter
    create_endpoint: Callable
    update_endpoint: Callable

    def __init__(self, api_router: APIRouter, create_endpoint: Callable, update_endpoint: Callable):
        self.blue_router = api_router
        self.create_endpoint = create_endpoint
        self.update_endpoint = update_endpoint
        # Load the modules into the memory and add the module routers into the main blue router.
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

    def _load_all_blue_from_db(self, blueprint_type: str = None) -> List[BlueprintNG]:
        """
        Load all the blueprints (ojb) from the database
        Args:
            blueprint_type (Optional[str]): The type of the blueprint to be retrieved

        Returns:
            The blueprint list (List[BlueprintNG]).
        """
        return [BlueprintNG.from_db(item) for item in self._load_all_blue_dict_from_db()]


    def create_blueprint(self, msg: Any, path: str) -> str:
        """
        Create a base, EMPTY, blueprint given the type of the blueprint.
        Then create a dedicated worker for the blueprint that spawns (ASYNC) the blueprint on the VIM.
        Args:
            msg: The message received from the user. The type change on the blueprint type. It is checked by fastAPI on the request.
            path: The blueprint-specific path, the last part of the URL for the creation request (e.g., /nfvcl/v2/api/blue/vyos ----> path='vyos')

        Returns:
            The ID of the created blueprint.
        """
        blue_id = generate_blueprint_id()
        # Check that a blueprint with that ID is not existing in the DB
        if self._load_blue_from_db(blue_id) is not None:
            raise BlueprintAlreadyExisting(blue_id)
        else:
            # Get the class, based on the blue type.
            BlueClass = get_blueprint_class(path)
            # Instantiate the object (creation of services is done by the worker)
            created_blue: BlueprintNG = BlueClass(blue_id, BlueprintsNgProviderNative) # TODO give the possibility to select the provider type
            # Saving the new blueprint to db
            created_blue.to_db()
            # Creating and starting the worker
            worker = BlueprintWorker(created_blue)
            worker.start_listening() # Start another PROCESS
            self.worker_collection[blue_id] = worker
            # Putting the creation message into the worker (the spawn happens asynch)
            worker.put_message(WorkerMessageType.DAY0, f'{path}', msg)
            return blue_id

    def delete_blueprint(self, blueprint_id: str) -> str:
        """
        Deletes the blueprint from the NFVCL (DB+worker)

        Args:
            blueprint_id: The ID of the blueprint to be deleted.

        Raises:
            BlueprintNotFoundException if blue does nor exist.
        """
        worker = self.get_worker(blueprint_id)
        worker.destroy_blueprint()
        self.worker_collection.pop(blueprint_id)
        return blueprint_id

    def delete_all_blueprints(self) -> None:
        """
        Deletes all blueprints in the NFVCL (DB+worker).
        """
        blue_list: List[dict] = self._load_all_blue_dict_from_db()

        for blue in blue_list:
            self.delete_blueprint(blueprint_id=blue['id'])

    def get_blueprint_summary_by_id(self, blueprint_id: str, detailed: bool = False) -> dict:
        """
        Retrieves the blueprint summary for the given blueprint ID.
        Args:
            blueprint_id: The blueprint to be retrieved.
            detailed: If true, return all the info saved in the database about the blueprints.

        Returns:
            The summary/details of a blueprint
        """
        blueprint: BlueprintNG = self._load_blue_from_db(blueprint_id)
        if blueprint is None:
            raise BlueprintNotFoundException(blueprint_id)
        return blueprint.to_dict(detailed)

    def get_blueprint_summary_list(self, blue_type: str, detailed: bool = False) -> List[dict]:
        """
        Retrieves the blueprint summary for the given blueprint ID.
        Args:
            blue_type:The optional filter to be used to filter results on a type basis (e.g., 'vyos').
            detailed: If true, return all the info saved in the database about the blueprints.

        Returns:
            The summary/details of all blueprints that satisfy the given filter.
        """
        if detailed:
            # Avoid to parse to model and then to dict
            return self._load_all_blue_dict_from_db()
        else:
            # Parsing to model to get summary instead of detailed
            blue_list = self._load_all_blue_from_db(blue_type)
            return [blueprint.to_dict(detailed=False) for blueprint in blue_list]

    def _load_modules(self):
        """
        IMPORT all blueprints modules in the NFVCL. When a module is loaded in the memory, decorators are read and executed.
        @declare_blue_type is used to actually load the info about every single module in the global collection.
        When all blueprint modules have been loaded, they are iterated by this function to create and add the router (for every blueprint type) to the main blue router.
        """
        importlib.import_module(BLUEPRINTS_MODULE_FOLDER)

        for module in get_registered_modules().values():
            BlueClass = getattr(importlib.import_module(module.module), module.class_name)
            self.blue_router.include_router(BlueClass.init_router(self.create_endpoint, self.update_endpoint, module.path))
