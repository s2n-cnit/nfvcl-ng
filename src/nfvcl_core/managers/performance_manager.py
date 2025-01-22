from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from nfvcl_core.database import BlueprintRepository
from nfvcl_core.database.performance_repository import PerformanceRepository
from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core.models.performance import BlueprintPerformanceType, BlueprintPerformance, BlueprintPerformanceOperation, \
    BlueprintPerformanceProviderCall


class PerformanceManager(GenericManager):
    """
    This class is used to manage the performance metrics collection
    """
    performance_dict: Dict[str, BlueprintPerformance]
    pending_operations: Dict[str, str] # blueprint_id: operation_id
    operations: Dict[str, BlueprintPerformanceOperation]
    provider_calls: Dict[str, BlueprintPerformanceProviderCall]

    def __init__(self, performance_repository: PerformanceRepository, blueprint_repository: BlueprintRepository):
        super().__init__()
        self._performance_repository = performance_repository
        self._blueprint_repository = blueprint_repository
        self.performance_dict = {}
        self.pending_operations = {}
        self.operations = {}
        self.provider_calls = {}

    def load(self):
        self._load_from_db()

    def _load_from_db(self):
        """
        Load the metrics already collected for the blueprints currently instantiated
        """
        for blueprint_to_load in self._blueprint_repository.get_all_dict():
            element = self._performance_repository.find_by_blueprint_id(blueprint_to_load['id']) # TODO doppia query al database
            if element:
                self.performance_dict[element.blueprint_id] = BlueprintPerformance.model_validate(element)
                self.logger.debug(f"Loaded performances for blueprint {blueprint_to_load['id']}")
            else:
                self.logger.warning(f"Unable to load performances for blueprint {blueprint_to_load['id']}")

    def _persist_to_db(self):
        """
        Persist the collected metrics to the mongo db
        """
        for blueid in self.performance_dict.keys():
            self._performance_repository.update_blueprint_performance(self.performance_dict[blueid])

    def get_blue_performance(self, blueprint_id: str) -> BlueprintPerformance:
        """
        Get the performance metrics for the blueprint
        Args:
            blueprint_id: Blueprint id

        Returns: A BlueprintPerformance instance for the blueprint
        """
        element = self._performance_repository.find_by_blueprint_id(blueprint_id)
        if element:
            return BlueprintPerformance.model_validate(element)
        raise ValueError(f"No performance metrics found for blueprint '{blueprint_id}'")

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
        blueprint_performance = BlueprintPerformance(blueprint_id=blueprint_id, start=datetime.now(timezone.utc), blueprint_type=blueprint_type)
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
            self.logger.warning("Skipping operation performance for unknown blueprint")
            return None
        op_id = str(uuid.uuid4())
        blueprint_operation = BlueprintPerformanceOperation(id=op_id, op_name=op_name, type=operation_type, start=datetime.now(timezone.utc))
        self.performance_dict[blueprint_id].operations.append(blueprint_operation)
        self.operations[op_id] = blueprint_operation
        if blueprint_id in self.pending_operations:
            #raise Exception("Multiple operation pending")
            self.logger.error("Multiple operation pending, replacing with newer one")
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
            self.logger.warning("Skipping operation performance for unknown operation or blueprint")
            return
        operation.end = datetime.now(timezone.utc)
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
            self.logger.warning("Skipping provider call performance for unknown operation")
            return None
        provider_call_id = str(uuid.uuid4())
        operation = self.operations[operation_id]
        blueprint_performance_provider_call = BlueprintPerformanceProviderCall(id=provider_call_id, method_name=method_name, info=info, start=datetime.now(timezone.utc))
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
            self.logger.warning("Skipping provider call performance for unknown operation")
            return
        provider_call = self.provider_calls[provider_call_id]
        provider_call.end = datetime.now(timezone.utc)
        provider_call.duration = round((provider_call.end - provider_call.start).total_seconds() * 1000)

    def delete_performance(self, blueprint_id: str):
        """
        Delete the performance metrics for a blueprint
        Args:
            blueprint_id: The blueprint id
        """
        if blueprint_id in self.performance_dict:
            del self.performance_dict[blueprint_id]
            self._performance_repository.delete_by_blueprint_id(blueprint_id)
        else:
            raise ValueError(f"No performance metrics found for blueprint '{blueprint_id}'")
