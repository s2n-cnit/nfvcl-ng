from typing import Optional

from nfvcl_core.database.database_repository import DatabaseRepository
from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_core.models.performance import BlueprintPerformance


class PerformanceRepository(DatabaseRepository[BlueprintPerformance]):
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, "performances", data_type=BlueprintPerformance)

    def find_by_blueprint_id(self, blueprint_id: str) -> Optional[BlueprintPerformance]:
        try:
            return self.find_one({'blueprint_id': blueprint_id})
        except Exception as e:
            return None

    def update_blueprint_performance(self, blueprint_performance: BlueprintPerformance) -> BlueprintPerformance:
        self.collection.update_one({ "blueprint_id": blueprint_performance.blueprint_id }, { "$set": blueprint_performance.model_dump()}, upsert=True)
        return blueprint_performance

    def delete_by_blueprint_id(self, blueprint_id: str):
        self.collection.delete_one({'blueprint_id': blueprint_id})
