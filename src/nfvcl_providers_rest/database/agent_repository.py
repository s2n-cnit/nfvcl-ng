from typing import Optional, List

from nfvcl_core.database.database_repository import DatabaseRepository
from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_providers_rest.models.db import NFVCLProviderAgent, NFVCLProviderResourceGroup


class NFVCLProviderAgentRepository(DatabaseRepository[NFVCLProviderAgent]):
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, "agents", data_type = NFVCLProviderAgent)

    def get_agent_data(self, agent_uuid: str) -> NFVCLProviderAgent:
        return self.find_one_safe({'uuid': agent_uuid})

    def get_resource_group(self, rg_id: str, agent_uuid: str) -> Optional[NFVCLProviderResourceGroup]:
        agent_data = self.get_agent_data(agent_uuid)
        if agent_data:
            return agent_data.resource_groups.get(rg_id)
        return None

    def update_all(self, agent_data_list: List[NFVCLProviderAgent]):
        for agent_data in agent_data_list:
            self.collection.update_one({'uuid': agent_data.uuid}, {'$set': agent_data.model_dump()})
