import copy
from typing import Optional, Any, List, Callable, Dict

from pydantic import Field

from nfvcl_core_models.network.network_models import PduModel, PduLockType, PduLock
from nfvcl_core_models.network.network_models import PduType
from nfvcl_common.utils.blue_utils import get_class_from_path
from nfvcl_core_models.providers.providers import ProviderData
from nfvcl_providers.provider_interface import ProviderInterface


class PDUProviderData(ProviderData):
    locked_pdus_by_blueprint: Dict[str, List[PduModel]] = Field(default_factory=dict)


class PDUProviderException(Exception):
    pass


class PDUProvider(ProviderInterface):
    data: PDUProviderData

    def __init__(self, topology_manager, pdu_manager, persistence_function: Optional[Callable] = None):
        super().__init__(persistence_function)
        self.topology_manager = topology_manager
        self.pdu_manager = pdu_manager

    def init(self):
        self.data: PDUProviderData = PDUProviderData()

    def _add_pdu_to_locked(self, blueprint_id: str, pdu: PduModel):
        if blueprint_id not in self.data.locked_pdus_by_blueprint:
            self.data.locked_pdus_by_blueprint[blueprint_id] = []
        self.data.locked_pdus_by_blueprint[blueprint_id].append(pdu)

    def _remove_pdu_from_locked(self, blueprint_id: str, pdu: PduModel):
        if blueprint_id in self.data.locked_pdus_by_blueprint:
            self.data.locked_pdus_by_blueprint[blueprint_id].remove(pdu)

    def find_pdu(self, area: int, pdu_type: PduType, instance_type: Optional[str] = None, name: Optional[str] = None) -> PduModel:
        """
        Find a PDU given the search parameters
        Args:
            area: Area of the PDU
            pdu_type: Type of the PDU
            instance_type: Instance type of the PDU, optional
            name: Name of the PDU, optional, may be needed if there are multiple PDUs of the same type in the same area
        Returns: The PDU if exactly one is found
        """
        found = self.find_pdus(area, pdu_type, instance_type)

        if name:
            found = list(filter(lambda x: x.name == name, found))

        if len(found) == 0:
            raise PDUProviderException(f"No PDU found with area {area} of type {pdu_type} and with name '{name}' (None mean that the name was not used to find the PDU)")
        if len(found) > 1:
            raise PDUProviderException(f"Found multiple PDUs with area {area} of type {pdu_type}, the name need to be used in this case to choose one")
        return found[0]

    def find_pdus(self, area: int, pdu_type: PduType, instance_type: Optional[str] = None) -> List[PduModel]:
        """
        Find a PDU given the search parameters
        Args:
            area: Area of the PDU
            pdu_type: Type of the PDU
            instance_type: Instance type of the PDU, optional

        Returns: List of PDUs that match the search parameters
        """
        all_pdus = self.topology_manager.get_topology().get_pdus()

        filtered_by_area = list(filter(lambda x: x.area == area, all_pdus))
        filtered_by_type = list(filter(lambda x: x.type == pdu_type, filtered_by_area))

        if instance_type:
            found = list(filter(lambda x: x.instance_type == instance_type, filtered_by_type))
        else:
            found = filtered_by_type

        if len(found) == 0:
            raise PDUProviderException(f"No PDU found with area {area} of type {pdu_type}")
        return found

    def find_by_name(self, name: str) -> PduModel:
        all_pdus = self.topology_manager.get_topology().get_pdus()

        results = list(filter(lambda x: x.name == name, all_pdus))
        if len(results) == 0:
            raise PDUProviderException(f"No PDU found with name '{name}'")
        return results[0]

    def is_pdu_locked(self, pdu_model: PduModel, lock_type: PduLockType) -> bool:
        """
        Check if a PDU is locked
        Args:
            lock_type: Lock type to check
            pdu_model: Model of the PDU to check

        Returns: True if the PDU is locked, False otherwise
        """
        for lock in pdu_model.locked_list_by:
            if lock.type == lock_type:
                return True
        return False

    def is_pdu_locked_by_blueprint(self, pdu_model: PduModel, lock_type: PduLockType, blueprint_id: str) -> bool:
        """
        Check if a PDU is locked
        Args:
            lock_type: Lock type to check
            pdu_model: Model of the PDU to check
            blueprint_id: Blueprint id

        Returns: True if the PDU is locked, False otherwise
        """
        for pdu in pdu_model.locked_list_by:
            if pdu.blueprint_id == blueprint_id and pdu.type == lock_type:
                return True
        return False

    def lock_pdu(self, pdu_model: PduModel, lock_type: PduLockType, blueprint_id: str) -> PduModel:
        """
        Lock a PDU
        Args:
            lock_type: Lock type to lock the PDU with
            pdu_model: Model of the PDU to lock
            blueprint_id: Blueprint id

        Returns: Updated PDU model
        """
        if not self.is_pdu_locked(pdu_model, lock_type):
            lock = PduLock(
                type=lock_type,
                blueprint_id=blueprint_id
            )
            pdu_model.locked_list_by.append(lock)
            self._add_pdu_to_locked(blueprint_id, pdu_model)
        else:
            for lock in pdu_model.locked_list_by:
                if lock.type == lock_type:
                    raise PDUProviderException(f"PDU {pdu_model.name} already locked by blueprint {lock.blueprint_id}")

        self.topology_manager.update_pdu(pdu_model)
        self.save_to_db()
        return pdu_model

    def unlock_pdu(self, pdu_model: PduModel, lock_type: PduLockType, blueprint_id: str) -> PduModel:
        """
        Unlock a PDU, need to be locked by the blueprint requesting to unlock
        Args:
            lock_type: Lock type to unlock the PDU with
            pdu_model: Model of the PDU to unlock
            blueprint_id: Blueprint id

        Returns: Updated PDU model
        """
        if self.is_pdu_locked(pdu_model, lock_type):
            for lock in pdu_model.locked_list_by:
                if lock.type == lock_type:
                    if lock.blueprint_id == blueprint_id:
                        pdu_model.locked_list_by.remove(lock)
                        if len(pdu_model.locked_list_by) == 0:
                            self._remove_pdu_from_locked(blueprint_id, pdu_model)
                    else:
                        raise PDUProviderException(f"The PDU is locked by another blueprint: {lock.blueprint_id}")
        else:
            raise PDUProviderException(f"PDU {pdu_model.name} is not locked")

        self.topology_manager.update_pdu(pdu_model)
        self.save_to_db()
        return pdu_model

    def get_pdu_configurator(self, pdu_model: PduModel, lock_type: PduLockType, blueprint_id: str) -> Any:
        """
        Get an instance of the configurator for the PDU, the PDU need to be locked by the blueprint requesting the configurator
        Args:
            lock_type: Lock type to get the configurator for
            pdu_model: Model of the PDU to get the configurator for
            blueprint_id: Blueprint id

        Returns: Instance of the configurator for the PDU (subclass of PDUConfigurator)
        """
        if self.is_pdu_locked(pdu_model, lock_type):
            if self.is_pdu_locked_by_blueprint(pdu_model, lock_type, blueprint_id):
                return get_class_from_path(self.pdu_manager.get_implementation(pdu_model.instance_type))(pdu_model)
        raise PDUProviderException(f"The PDU is not locked or locked by another blueprint: {pdu_model.locked_list_by}")

    def add_pdu(self, pdu: PduModel) -> PduModel:
        """
        Add a PDU to the topology
        Args:
            pdu: PDU to add

        Returns: The added PDU
        """
        self.topology_manager.create_pdu(pdu)
        return pdu

    def delete_pdu(self, pdu_id: str) -> None:
        """
        Delete a PDU from the topology
        Args:
            pdu_id: ID of the PDU to delete
        """
        self.topology_manager.delete_pdu(pdu_id)

    def cleanup_resource_group(self, blueprint_id: str):
        for pdu_to_unlock in copy.copy(self.data.locked_pdus_by_blueprint.get(blueprint_id, [])):
            try:
                updated_model = self.find_by_name(pdu_to_unlock.name)
                for lock in updated_model.locked_list_by:
                    self.unlock_pdu(updated_model, lock.type, blueprint_id)
            except Exception as e:
                self.logger.warning(f"Error unlocking PDU '{pdu_to_unlock.name}': {e}")
        self.data.locked_pdus_by_blueprint.pop(blueprint_id, None)
        self.save_to_db()
