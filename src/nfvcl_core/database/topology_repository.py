from nfvcl_core.database import DatabaseRepository
from nfvcl_core.managers import PersistenceManager
from nfvcl_core.models.topology_models import TopologyModel


class TopologyRepository(DatabaseRepository[TopologyModel]):
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, "topology", data_type=TopologyModel)

    def get_topology(self) -> TopologyModel:
        elements = self.get_all()
        return elements[0] if elements else None

    def save_topology(self, topology: TopologyModel) -> None:
        if self.collection.find_one({'id': topology.id}):
            self.collection.update_one({'id': topology.id}, {'$set': topology.model_dump()})
        else:
            self.collection.insert_one(topology.model_dump())
