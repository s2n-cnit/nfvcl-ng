from typing import Any, Optional, Callable, TYPE_CHECKING

from nfvcl_core_models.http_models import BlueprintNotFoundException
from nfvcl_providers.provider_interface import ProviderInterface

if TYPE_CHECKING:
    from nfvcl_core.managers.blueprint_manager import BlueprintManager
from nfvcl_core_models.providers.blueprint import BlueprintProviderData


class BlueprintProvider(ProviderInterface):
    data: BlueprintProviderData

    def __init__(self, blueprint_manager: BlueprintManager, persistence_function: Optional[Callable] = None):
        super().__init__(persistence_function)
        self.blueprint_manager = blueprint_manager

    def init(self):
        self.data: BlueprintProviderData = BlueprintProviderData()

    def create_blueprint(self, path: str, msg: Any, parent_id: str):
        blue_id = self.blueprint_manager.create_blueprint(path, msg, parent_id=parent_id)
        self.data.add_child_blueprint(parent_id, blue_id)
        self.save_to_db()
        return blue_id

    def delete_blueprint(self, blueprint_id: str, parent_id: str):
        self.blueprint_manager.delete_blueprint(blueprint_id, child_deletion=True)
        self.data.remove_child_blueprint(parent_id, blueprint_id)
        self.save_to_db()
        return blueprint_id

    def call_blueprint_function(self, blue_id: str, function_name: str, *args, **kwargs) -> Any:
        """
        Call a function on another blueprint
        Args:
            blue_id: Id of the blueprint to call on the function on
            function_name: Name of the function to call
            *args: args
            **kwargs: kwargs

        Returns: Result of the function call
        """
        self.logger.debug(f"Calling external function '{function_name}' on blueprint '{blue_id}', args={args}, kwargs={kwargs}")
        res = self.blueprint_manager.call_function(blue_id, function_name, *args, **kwargs)
        self.logger.debug(f"Result of external function '{function_name}' on blueprint '{blue_id}' = {res}")
        return res

    def cleanup_resource_group(self, blueprint_id: str):
        for blue_id in self.data.get_child_blueprints(blueprint_id):
            self.logger.warning(f"Deleting leftover deployed blueprint: {blue_id}")
            try:
                self.blueprint_manager.delete_blueprint(blue_id, child_deletion=True)
            except BlueprintNotFoundException:
                self.logger.warning(f"The blueprint {blue_id} was already deleted")
            except Exception as e:
                self.logger.error(f"Error deleting leftover deployed blueprint {blue_id}: {str(e)}")
        self.data.clear_child_blueprints(blueprint_id)
        self.save_to_db()
