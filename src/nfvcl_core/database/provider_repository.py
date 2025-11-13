from typing import Optional

from nfvcl_core.database.database_repository import DatabaseRepository
from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_core_models.providers.providers import ProviderDataAggregate


class ProviderDataRepository(DatabaseRepository[ProviderDataAggregate]):
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, "providers", data_type = ProviderDataAggregate)

    def save_provider_data(self, provider_data: ProviderDataAggregate):
        if self.collection.find_one({'blueprint_id': provider_data.blueprint_id}):
            self.collection.update_one({'blueprint_id': provider_data.blueprint_id}, {'$set': provider_data.model_dump()})
        else:
            self.collection.insert_one(provider_data.model_dump())

    def find_by_blueprint_id(self, blueprint_id: str) -> Optional[ProviderDataAggregate]:
        try:
            return self.find_one({'blueprint_id': blueprint_id})
        except Exception as e:
            return None

    def delete_by_blueprint_id(self, blueprint_id: str):
        return self.collection.delete_one({'blueprint_id': blueprint_id})
