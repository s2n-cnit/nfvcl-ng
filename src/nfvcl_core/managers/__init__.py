from dependency_injector.wiring import Provide, inject

from .generic_manager import GenericManager
from .persistence_manager import PersistenceManager
from .task_manager import TaskManager
from .event_manager import EventManager
from .topology_manager import TopologyManager
from .blueprint_manager import BlueprintManager
from .performance_manager import PerformanceManager
from .kubernetes_manager import KubernetesManager
from .pdu_manager import PDUManager
from nfvcl_core.containers import NFVCLContainer

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
