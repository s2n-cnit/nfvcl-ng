from nfvcl_core.database.database_repository import DatabaseRepository
from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_core_models.vim.vim_models import VimModel


class NFVCLProviderVimRepository(DatabaseRepository[VimModel]):
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, "vims", data_type = VimModel)

    def add_vim(self, vim_model: VimModel):
        self.collection.insert_one(vim_model.model_dump())

    def get_vim(self, vim_name: str) -> VimModel:
        return self.find_one({'name': vim_name})
