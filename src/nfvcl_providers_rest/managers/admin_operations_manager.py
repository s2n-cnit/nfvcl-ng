from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core.managers.task_manager import TaskManager
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.vim.vim_models import VimModel
from nfvcl_providers_rest.database.agent_repository import NFVCLProviderAgentRepository
from nfvcl_providers_rest.database.vim_repository import NFVCLProviderVimRepository


class AdminOperationsManager(GenericManager):
    def __init__(self, task_manager: TaskManager, vim_repository: NFVCLProviderVimRepository, agent_repository: NFVCLProviderAgentRepository, admin_uuid: str):
        super().__init__()
        self.task_manager = task_manager
        self.vim_repository = vim_repository
        self.agent_repository = agent_repository
        self.admin_uuid = admin_uuid

    def add_vim(self, vim: VimModel, agent_uuid: str):
        if agent_uuid != self.admin_uuid:
            raise NFVCLCoreException("Only admin can add new VIMs", http_equivalent_code=403)
        self.vim_repository.add_vim(vim)
        return vim
