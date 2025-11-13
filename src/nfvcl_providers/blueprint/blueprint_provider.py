from typing import Any, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from nfvcl_core.managers.blueprint_manager import BlueprintManager
from nfvcl_providers.blueprint_ng_provider_interface import BlueprintNGProviderInterface
from nfvcl_core_models.providers.blueprint import BlueprintProviderData


class BlueprintProvider(BlueprintNGProviderInterface):
    data: BlueprintProviderData

    def __init__(self, area: int, blueprint_id: str, blueprint_manager: BlueprintManager, persistence_function: Optional[Callable] = None):
        super().__init__(area, blueprint_id, persistence_function)
        self.blueprint_manager = blueprint_manager

    def init(self):
        self.data: BlueprintProviderData = BlueprintProviderData()

    def create_blueprint(self, path: str, msg: Any):
        blue_id = self.blueprint_manager.create_blueprint(path, msg, parent_id=self.blueprint_id)
        self.data.deployed_blueprints.append(blue_id)
        self.save_to_db()
        return blue_id

    def delete_blueprint(self, blueprint_id: str):
        self.blueprint_manager.delete_blueprint(blueprint_id)
        self.data.deployed_blueprints.remove(blueprint_id)
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

    def final_cleanup(self):
        for blue_id in self.data.deployed_blueprints:
            self.logger.warning(f"Deleting leftover deployed blueprint: {blue_id}")
            try:
                self.blueprint_manager.delete_blueprint(blue_id)
            except Exception as e:
                self.logger.error(f"Error deleting leftover deployed blueprint {blue_id}: {str(e)}")
        self.data.deployed_blueprints.clear()
        self.save_to_db()
