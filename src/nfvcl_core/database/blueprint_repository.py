from nfvcl_core.database.database_repository import DatabaseRepository
from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_core_models.blueprints.blueprint import BlueprintNGBaseModel


class BlueprintRepository(DatabaseRepository[BlueprintNGBaseModel]):
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, "blueprints", data_type = BlueprintNGBaseModel)

    def save_blueprint(self, blueprint: BlueprintNGBaseModel):
        if self.collection.find_one({'id': blueprint.id}):
            self.collection.update_one({'id': blueprint.id}, {'$set': blueprint.model_dump()})
        else:
            self.collection.insert_one(blueprint.model_dump())

    def delete_blueprint(self, blueprint_id: str):
        self.collection.delete_one({'id': blueprint_id})
