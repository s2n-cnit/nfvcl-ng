from __future__ import annotations

import datetime
import uuid
from typing import Dict, Optional

from pymongo import MongoClient
from verboselogs import VerboseLogger

from nfvcl.models.config_model import NFVCLConfigModel
from nfvcl.models.performance import BlueprintPerformanceType, BlueprintPerformance, BlueprintPerformanceOperation, \
    BlueprintPerformanceProviderCall
from nfvcl.utils.database import get_nfvcl_database
from nfvcl.utils.log import create_logger
from nfvcl.utils.util import get_nfvcl_config

logger: VerboseLogger = create_logger("PerformanceManager")

__performance_manager: PerformanceManager | None = None

nfvcl_config: NFVCLConfigModel = get_nfvcl_config()

def get_performance_manager() -> PerformanceManager:
    """
    Allow to retrieve the PerformanceManager (that can have only one instance)
    Returns:
        The performance manager
    """
    global __performance_manager
    if __performance_manager is not None:
        return __performance_manager
    else:
        __performance_manager = PerformanceManager()
        return __performance_manager


class PerformanceManager:
    """
    This class is used to manage the performance metrics collection
    """
    performance_dict: Dict[str, BlueprintPerformance]
    pending_operations: Dict[str, str] # blueprint_id: operation_id
    operations: Dict[str, BlueprintPerformanceOperation]
    provider_calls: Dict[str, BlueprintPerformanceProviderCall]

    def __init__(self):
        super().__init__()
        self.performance_dict = {}
        self.pending_operations = {}
        self.operations = {}
        self.provider_calls = {}

        mongo_client: MongoClient = get_nfvcl_database().mongo_client
        db = mongo_client.get_database(nfvcl_config.mongodb.db)

        if 'performance' not in db.list_collection_names():
            db.create_collection('performance')

        self.performance_collection = db.get_collection('performance')
        self.blue_inst_collection = db.get_collection('blue-inst-v2')

        self._load_from_db()

    def _load_from_db(self):
        """
        Load the metrics already collected for the blueprints currently instantiated
        """
        blueprints_to_load = self.blue_inst_collection.find()
        for blueprint_to_load in blueprints_to_load:
            element = self.performance_collection.find_one({"blueprint_id": blueprint_to_load["id"]})
            if element:
                self.performance_dict[element['blueprint_id']] = BlueprintPerformance.model_validate(element)
                logger.debug(f"Loaded performances for blueprint {element['blueprint_id']}")
            else:
                logger.warning(f"Unable to load performances for blueprint {blueprint_to_load['id']}")

    def _persist_to_db(self):
        """
        Persist the collected metrics to the mongo db
        """
        for blueid in self.performance_dict.keys():
            self.performance_collection.update_one({ "blueprint_id": blueid }, { "$set": self.performance_dict[blueid].model_dump()}, upsert=True)

    def get_pending_operation_id(self, blueprint_id: str) -> Optional[str]:
        """
        Get the current pending operation id for a blueprint
        Args:
            blueprint_id: The blueprint of which to get the pending operation id

        Returns: The pending operation id
        """
        if blueprint_id in self.pending_operations:
            return self.pending_operations[blueprint_id]
        return None

    def add_blueprint(self, blueprint_id: str, blueprint_type: str):
        """
        Add a new blueprint to the metrics collection
        Args:
            blueprint_id: ID of the blueprint
            blueprint_type: The type of the blueprint
        """
        blueprint_performance = BlueprintPerformance(blueprint_id=blueprint_id, start=datetime.datetime.utcnow(), blueprint_type=blueprint_type)
        self.performance_dict[blueprint_id] = blueprint_performance

    def start_operation(self, blueprint_id: str, operation_type: BlueprintPerformanceType, op_name: str) -> Optional[str]:
        """
        Log the start of a new operation on a blueprint
        Args:
            blueprint_id: The blueprint id
            operation_type: The operation type (day0, day2)
            op_name: The name of the operation

        Returns: The operation id
        """
        if blueprint_id not in self.performance_dict:
            logger.warning("Skipping operation performance for unknown blueprint")
            return None
        op_id = str(uuid.uuid4())
        blueprint_operation = BlueprintPerformanceOperation(id=op_id, op_name=op_name, type=operation_type, start=datetime.datetime.utcnow())
        self.performance_dict[blueprint_id].operations.append(blueprint_operation)
        self.operations[op_id] = blueprint_operation
        if blueprint_id in self.pending_operations:
            #raise Exception("Multiple operation pending")
            logger.error("Multiple operation pending, replacing with newer one")
        self.pending_operations[blueprint_id] = op_id
        return op_id

    def _find_operation(self, operation_id: str) -> (BlueprintPerformanceOperation, str):
        for blueprint_performance in self.performance_dict.values():
            for blueprint_operation in blueprint_performance.operations:
                if blueprint_operation.id == operation_id:
                    return blueprint_operation, blueprint_performance.blueprint_id
        return None, None

    def end_operation(self, operation_id: str):
        """
        Log the end of an operation on a blueprint
        Args:
            operation_id: The operation id
        """
        operation, blueprint_id = self._find_operation(operation_id)
        if operation is None:
            logger.warning("Skipping operation performance for unknown operation or blueprint")
            return
        operation.end = datetime.datetime.utcnow()
        operation.duration = round((operation.end - operation.start).total_seconds() * 1000)
        del self.pending_operations[blueprint_id]
        self._persist_to_db()

    def start_provider_call(self, operation_id: Optional[str], method_name: str, info: Dict[str, str]) -> Optional[str]:
        """
        Log a call to a provider operation
        Args:
            operation_id: The operation in which this provider call occur
            method_name: The name of the method called on the provider
            info: Additional information about the call

        Returns: Provider call id
        """
        if operation_id is None or operation_id not in self.operations:
            logger.warning("Skipping provider call performance for unknown operation")
            return None
        provider_call_id = str(uuid.uuid4())
        operation = self.operations[operation_id]
        blueprint_performance_provider_call = BlueprintPerformanceProviderCall(id=provider_call_id, method_name=method_name, info=info, start=datetime.datetime.utcnow())
        self.provider_calls[provider_call_id] = blueprint_performance_provider_call
        operation.provider_calls.append(blueprint_performance_provider_call)
        return provider_call_id

    def end_provider_call(self, provider_call_id: str):
        """
        Log the end of a provider call
        Args:
            provider_call_id: The id of the provider call
        """
        if provider_call_id not in self.provider_calls:
            logger.warning("Skipping provider call performance for unknown operation")
            return
        provider_call = self.provider_calls[provider_call_id]
        provider_call.end = datetime.datetime.utcnow()
        provider_call.duration = round((provider_call.end - provider_call.start).total_seconds() * 1000)
