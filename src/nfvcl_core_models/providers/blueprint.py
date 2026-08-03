from typing import List, Dict

from pydantic import Field

from nfvcl_core_models.providers.providers import ProviderData


class BlueprintProviderData(ProviderData):
    child_blueprints: Dict[str, List[str]] = Field(default_factory=dict)

    def get_child_blueprints(self, parent_blueprint_id: str) -> List[str]:
        return self.child_blueprints.get(parent_blueprint_id, [])

    def add_child_blueprint(self, parent_blueprint_id: str, child_blueprint_id: str):
        if parent_blueprint_id not in self.child_blueprints:
            self.child_blueprints[parent_blueprint_id] = []
        self.child_blueprints[parent_blueprint_id].append(child_blueprint_id)

    def remove_child_blueprint(self, parent_blueprint_id: str, child_blueprint_id: str):
        if parent_blueprint_id in self.child_blueprints:
            self.child_blueprints[parent_blueprint_id].remove(child_blueprint_id)
            if not self.child_blueprints[parent_blueprint_id]:
                self.child_blueprints.pop(parent_blueprint_id, None)

    def clear_child_blueprints(self, parent_blueprint_id: str):
        self.child_blueprints.pop(parent_blueprint_id, None)

class BlueprintProviderException(Exception):
    pass
