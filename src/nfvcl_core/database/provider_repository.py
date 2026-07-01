from typing import List, Optional

from nfvcl_core.database.database_repository import DatabaseRepository
from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_core_models.providers.providers import ProviderData, ProviderDataDocument


class ProviderDataRepository(DatabaseRepository[ProviderDataDocument]):
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, "providers", data_type=ProviderDataDocument)

    def save_provider_type_data(self, provider_type: str, provider_data: ProviderData):
        document = ProviderDataDocument(provider_type=provider_type, data=provider_data)
        self.collection.update_one(
            {'provider_type': provider_type},
            {'$set': document.model_dump(mode="json")},
            upsert=True
        )

    def find_by_provider_type(
        self,
        provider_type: str,
        data_type: type[ProviderData] = ProviderData
    ) -> Optional[ProviderData]:
        result = self.collection.find_one({'provider_type': provider_type}, projection={'_id': False})
        if result is None:
            return None
        return data_type.model_validate(result.get("data", {}))

    def delete_by_provider_type(self, provider_type: str):
        return self.collection.delete_one({'provider_type': provider_type})

    def get_all(self) -> List[ProviderDataDocument]:
        return [
            ProviderDataDocument.model_validate(element)
            for element in self.collection.find({'provider_type': {'$exists': True}}, projection={'_id': False})
        ]

    def get_all_dict(self) -> List[dict]:
        return [
            element
            for element in self.collection.find({'provider_type': {'$exists': True}}, projection={'_id': False})
        ]
