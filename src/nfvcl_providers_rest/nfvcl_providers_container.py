from dependency_injector import containers, providers

from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_core.managers.task_manager import TaskManager
from nfvcl_providers_rest.config import NFVCLProvidersConfigModel
from nfvcl_providers_rest.database.agent_repository import NFVCLProviderAgentRepository
from nfvcl_providers_rest.database.vim_repository import NFVCLProviderVimRepository
from nfvcl_providers_rest.managers.admin_operations_manager import AdminOperationsManager
from nfvcl_providers_rest.managers.virtualization_manager import VirtualizationManager


class NFVCLProvidersContainer(containers.DeclarativeContainer):
    config: providers.Configuration[NFVCLProvidersConfigModel] = providers.Configuration()

    persistence_manager = providers.Singleton(
        PersistenceManager,
        host=config.mongodb.host,
        port=config.mongodb.port,
        db=config.mongodb.db,
        username=config.mongodb.username,
        password=config.mongodb.password,
        migration_base_class=None
    )

    task_manager = providers.Singleton(
        TaskManager,
        worker_count=config.nfvcl_providers.workers
    )

    vim_repository = providers.Singleton(
        NFVCLProviderVimRepository,
        persistence_manager=persistence_manager
    )

    agent_repository = providers.Singleton(
        NFVCLProviderAgentRepository,
        persistence_manager=persistence_manager
    )

    admin_operations_manager = providers.Singleton(
        AdminOperationsManager,
        task_manager=task_manager,
        agent_repository=agent_repository,
        vim_repository=vim_repository,
        admin_uuid=config.nfvcl_providers.admin_uuid
    )

    virtualization_manager = providers.Singleton(
        VirtualizationManager,
        task_manager=task_manager,
        agent_repository=agent_repository,
        vim_repository=vim_repository,
    )
