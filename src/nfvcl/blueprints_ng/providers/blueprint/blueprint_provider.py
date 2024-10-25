from typing import Any, List

from pydantic import Field

from nfvcl.blueprints_ng.providers.blueprint_ng_provider_interface import BlueprintNGProviderData, BlueprintNGProviderInterface
from nfvcl.models.blueprint_ng.worker_message import BlueprintOperationCallbackModel


class BlueprintProviderData(BlueprintNGProviderData):
    deployed_blueprints: List[str] = Field(default_factory=list)


class BlueprintProviderException(Exception):
    pass

class BlueprintProvider(BlueprintNGProviderInterface):
    data: BlueprintProviderData

    def init(self):
        from nfvcl.blueprints_ng.lcm.blueprint_manager import get_blueprint_manager
        self.blueprint_manager = get_blueprint_manager()
        self.data: BlueprintProviderData = BlueprintProviderData()

    def create_blueprint(self, msg: Any, path: str):
        blue_id = self.blueprint_manager.create_blueprint(msg, path, wait=True, parent_id=self.blueprint_id)
        self.data.deployed_blueprints.append(blue_id)
        self.save_to_db()
        return blue_id

    def delete_blueprint(self, blueprint_id: str):
        self.blueprint_manager.delete_blueprint(blueprint_id, wait=True)
        self.data.deployed_blueprints.remove(blueprint_id)
        self.save_to_db()
        return blueprint_id

    def call_blueprint_function(self, blue_id: str, function_name: str, *args, **kwargs) -> BlueprintOperationCallbackModel:
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
        res = self.blueprint_manager.get_worker(blue_id).call_function_sync(function_name, *args, **kwargs)
        self.logger.debug(f"Result of external function '{function_name}' on blueprint '{blue_id}' = {res}")
        return res

    def final_cleanup(self):
        for blue_id in self.data.deployed_blueprints:
            self.logger.warning(f"Deleting leftover deployed blueprint: {blue_id}")
            try:
                self.blueprint_manager.delete_blueprint(blue_id, wait=True)
            except Exception as e:
                self.logger.error(f"Error deleting leftover deployed blueprint {blue_id}: {str(e)}")
        self.data.deployed_blueprints.clear()
        self.save_to_db()
