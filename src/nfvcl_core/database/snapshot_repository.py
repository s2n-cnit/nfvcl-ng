from nfvcl_core.database.database_repository import DatabaseRepository
from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_core_models.blueprints.blueprint import BlueprintNGBaseModel


class SnapshotRepository(DatabaseRepository[BlueprintNGBaseModel]):
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, "blue-snapshots", data_type=BlueprintNGBaseModel)

    def save_snapshot(self, blueprint_snapshot: BlueprintNGBaseModel):
        """
        Save a blueprint snapshot in the database
        Args:
            blueprint_snapshot: The blueprint snapshot to save
        """
        if self.collection.find_one({'id': blueprint_snapshot.id}):
            self.collection.update_one({'id': blueprint_snapshot.id}, {'$set': blueprint_snapshot.model_dump()})
        else:
            self.collection.insert_one(blueprint_snapshot.model_dump())

    def delete_snapshot(self, snapshot_name: str):
        """
        Delete a blueprint snapshot from the database
        Args:
            snapshot_name: The name of the snapshot to delete
        """
        self.collection.delete_one({'id': snapshot_name})

    def get_snapshot(self, snapshot_name: str) -> BlueprintNGBaseModel | None:
        """
        Get a blueprint snapshot from the database
        Args:
            snapshot_name: The name of the snapshot to get
        """
        return self.find_one_safe({'id': snapshot_name})
