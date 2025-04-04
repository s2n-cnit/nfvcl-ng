from dependency_injector.wiring import Provide, inject

from .generic_manager import GenericManager as GenericManager
from .persistence_manager import PersistenceManager
from .task_manager import TaskManager
from .event_manager import EventManager
from .topology_manager import TopologyManager as TopologyManager
from .blueprint_manager import BlueprintManager
from .performance_manager import PerformanceManager
from .pdu_manager import PDUManager as PDUManager
from .vim_clients_manager import VimClientsManager
from nfvcl_core.containers.nfvcl_container import NFVCLContainer


@inject
def get_blueprint_manager(_blueprint_manager: BlueprintManager = Provide[NFVCLContainer.blueprint_manager]) -> BlueprintManager:
    return _blueprint_manager

@inject
def get_performance_manager(_performance_manager: PerformanceManager = Provide[NFVCLContainer.performance_manager]) -> PerformanceManager:
    return _performance_manager

@inject
def get_task_manager(_task_manager: TaskManager = Provide[NFVCLContainer.task_manager]) -> TaskManager:
    return _task_manager

@inject
def get_event_manager(_event_manager: EventManager = Provide[NFVCLContainer.event_manager]) -> EventManager:
    return _event_manager

@inject
def get_persistence_manager(_persistence_manager: PersistenceManager = Provide[NFVCLContainer.persistence_manager]) -> PersistenceManager:
    return _persistence_manager

@inject
def get_vim_clients_manager(_vim_clients_manager: VimClientsManager = Provide[NFVCLContainer.vim_clients_manager]) -> VimClientsManager:
    return _vim_clients_manager
