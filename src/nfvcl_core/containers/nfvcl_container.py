from dependency_injector import containers, providers

from nfvcl_core.database.provider_repository import ProviderDataRepository
from nfvcl_core.database.snapshot_repository import SnapshotRepository
from nfvcl_core.managers.blueprint_manager import BlueprintManager
from nfvcl_core.managers.event_manager import EventManager
from nfvcl_core.managers.monitoring_manager import MonitoringManager
from nfvcl_core.managers.performance_manager import PerformanceManager
from nfvcl_core.managers.persistence_manager import PersistenceManager
from nfvcl_core.managers.task_manager import TaskManager
from nfvcl_core.managers.topology_manager import TopologyManager
from nfvcl_core.managers.vim_clients_manager import VimClientsManager
from nfvcl_core_models.config import NFVCLConfigModel
from nfvcl_core.database.topology_repository import TopologyRepository
from nfvcl_core.database.blueprint_repository import BlueprintRepository
from nfvcl_core.database.performance_repository import PerformanceRepository
from nfvcl_core.database.user_repository import  UserRepository
from nfvcl_core.managers.kubernetes_manager import KubernetesManager
from nfvcl_core.managers.pdu_manager import PDUManager
from nfvcl_core.managers.user_manager import UserManager


class NFVCLContainer(containers.DeclarativeContainer):
    config: providers.Configuration[NFVCLConfigModel] = providers.Configuration()

    persistence_manager = providers.Singleton(
        PersistenceManager,
        host=config.mongodb.host,
        port=config.mongodb.port,
        db=config.mongodb.db,
        username=config.mongodb.username,
        password=config.mongodb.password
    )

    task_manager = providers.Singleton(
        TaskManager,
        worker_count=config.nfvcl.workers
    )

    event_manager = providers.Singleton(
        EventManager,
        task_manager=task_manager,
        redis_host=config.redis.host,
        redis_port=config.redis.port,
        redis_password=config.redis.password
    )

    topology_repository = providers.Singleton(
        TopologyRepository,
        persistence_manager=persistence_manager
    )

    blueprint_repository = providers.Singleton(
        BlueprintRepository,
        persistence_manager=persistence_manager
    )

    provider_repository = providers.Singleton(
        ProviderDataRepository,
        persistence_manager=persistence_manager
    )

    snapshot_repository = providers.Singleton(
        SnapshotRepository,
        persistence_manager=persistence_manager
    )

    performance_repository = providers.Singleton(
        PerformanceRepository,
        persistence_manager=persistence_manager
    )

    user_repository = providers.Singleton(
        UserRepository,
        persistence_manager=persistence_manager
    )

    topology_manager = providers.Singleton(
        TopologyManager,
        topology_repository=topology_repository
    )

    vim_clients_manager = providers.Singleton(
        VimClientsManager,
        topology_manager=topology_manager
    )

    monitoring_manager = providers.Singleton(
        MonitoringManager,
        topology_manager=topology_manager
    )

    pdu_manager = providers.Singleton(
        PDUManager,
    )

    performance_manager = providers.Singleton(
        PerformanceManager,
        performance_repository=performance_repository,
        blueprint_repository=blueprint_repository
    )

    blueprint_manager = providers.Singleton(
        BlueprintManager,
        provider_repository=provider_repository,
        snapshot_repository=snapshot_repository,
        blueprint_repository=blueprint_repository,
        topology_manager=topology_manager,
        pdu_manager=pdu_manager,
        performance_manager=performance_manager,
        event_manager=event_manager,
        vim_clients_manager=vim_clients_manager
    )

    kubernetes_manager = providers.Singleton(
        KubernetesManager,
        blueprint_manager=blueprint_manager,
        topology_manager=topology_manager,
        event_manager=event_manager
    )

    user_manager = providers.Singleton(
        UserManager,
        user_repository=user_repository
    )




