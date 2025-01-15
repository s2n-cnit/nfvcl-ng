from dependency_injector import containers, providers

from nfvcl_core.config import NFVCLConfigModel, load_nfvcl_config
from nfvcl_core.database import TopologyRepository, BlueprintRepository, PerformanceRepository
from nfvcl_core.managers import PersistenceManager, TopologyManager, BlueprintManager, TaskManager, PerformanceManager, EventManager
from nfvcl_core.managers.kubernetes_manager import KubernetesManager
from nfvcl_core.managers.pdu_manager import PDUManager


class NFVCLContainer(containers.DeclarativeContainer):
    config: providers.Configuration[NFVCLConfigModel] = providers.Configuration()
    config.from_pydantic(load_nfvcl_config())

    persistence_manager = providers.Singleton(
        PersistenceManager,
        host=config.mongodb.host,
        port=config.mongodb.port,
        db=config.mongodb.db,
        username=config.mongodb.username,
        password=config.mongodb.password # I was missing :(((((
    )

    task_manager = providers.Singleton(
        TaskManager,
        worker_count=4
    )

    event_manager = providers.Singleton(
        EventManager,
        task_manager=task_manager,
        redis_host=config.redis.host,
        redis_port=config.redis.port,
    )

    topology_repository = providers.Singleton(
        TopologyRepository,
        persistence_manager=persistence_manager
    )

    blueprint_repository = providers.Singleton(
        BlueprintRepository,
        persistence_manager=persistence_manager
    )

    performance_repository = providers.Singleton(
        PerformanceRepository,
        persistence_manager=persistence_manager
    )

    topology_manager = providers.Singleton(
        TopologyManager,
        topology_repository=topology_repository
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
        blueprint_repository=blueprint_repository,
        topology_manager=topology_manager,
        pdu_manager=pdu_manager,
        performance_manager=performance_manager,
        event_manager=event_manager
    )

    kubernetes_manager = providers.Singleton(
        KubernetesManager,
        blueprint_manager=blueprint_manager,
        topology_manager=topology_manager,
        event_manager=event_manager
    )




