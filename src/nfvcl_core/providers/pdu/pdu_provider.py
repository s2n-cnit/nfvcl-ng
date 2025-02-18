import copy
from typing import Optional, Any, List

from pydantic import Field

from nfvcl_core.providers.blueprint_ng_provider_interface import BlueprintNGProviderData, BlueprintNGProviderInterface
from nfvcl_core_models.network import PduModel
from nfvcl_core_models.network.network_models import PduType
from nfvcl_core.utils.blue_utils import get_class_from_path


class PDUProviderData(BlueprintNGProviderData):
    locked_pdus: List[PduModel] = Field(default_factory=list)


class PDUProviderException(Exception):
    pass


class PDUProvider(BlueprintNGProviderInterface):
    data: PDUProviderData

    def init(self):
        self.data: PDUProviderData = PDUProviderData()

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
        all_pdus = self.topology.get_pdus()

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
        all_pdus = self.topology.get_pdus()

        results = list(filter(lambda x: x.name == name, all_pdus))
        if len(results) == 0:
            raise PDUProviderException(f"No PDU found with name '{name}'")
        return results[0]

    def is_pdu_locked(self, pdu_model: PduModel) -> bool:
        """
        Check if a PDU is locked
        Args:
            pdu_model: Model of the PDU to check

        Returns: True if the PDU is locked, False otherwise
        """
        return pdu_model.locked_by is not None

    def is_pdu_locked_by_current_blueprint(self, pdu_model: PduModel) -> bool:
        """
        Check if a PDU is locked
        Args:
            pdu_model: Model of the PDU to check

        Returns: True if the PDU is locked, False otherwise
        """
        return pdu_model.locked_by == self.blueprint_id

    def lock_pdu(self, pdu_model: PduModel) -> PduModel:
        """
        Lock a PDU
        Args:
            pdu_model: Model of the PDU to lock

        Returns: Updated PDU model
        """
        if not self.is_pdu_locked(pdu_model):
            pdu_model.locked_by = self.blueprint_id
            self.data.locked_pdus.append(pdu_model)
        else:
            raise PDUProviderException(f"PDU {pdu_model.name} already locked by blueprint {pdu_model.locked_by}")

        self.topology_manager.update_pdu(pdu_model)
        self.save_to_db()
        return pdu_model

    def unlock_pdu(self, pdu_model: PduModel) -> PduModel:
        """
        Unlock a PDU, need to be locked by the blueprint requesting to unlock
        Args:
            pdu_model: Model of the PDU to unlock

        Returns: Updated PDU model
        """
        if self.is_pdu_locked(pdu_model):
            if pdu_model.locked_by == self.blueprint_id:
                pdu_model.locked_by = None
                self.data.locked_pdus.remove(pdu_model)
            else:
                raise PDUProviderException(f"The PDU is locked by another blueprint: {pdu_model.locked_by}")
        else:
            raise PDUProviderException(f"PDU {pdu_model.name} is not locked")

        self.topology_manager.update_pdu(pdu_model)
        self.save_to_db()
        return pdu_model

    # The type should be Type[PDUConfigurator] but PYCharm doesn't understand it
    def get_pdu_configurator(self, pdu_model: PduModel) -> Any:
        """
        Get an instance of the configurator for the PDU, the PDU need to be locked by the blueprint requesting the configurator
        Args:
            pdu_model: Model of the PDU to get the configurator for

        Returns: Instance of the configurator for the PDU (subclass of PDUConfigurator)
        """
        if self.is_pdu_locked(pdu_model):
            if pdu_model.locked_by == self.blueprint_id:
                return get_class_from_path(self.pdu_manager.get_implementation(pdu_model.instance_type))(pdu_model)
        raise PDUProviderException(f"The PDU is not locked or locked by another blueprint: {pdu_model.locked_by}")

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

    def final_cleanup(self):
        for pdu_to_unlock in copy.copy(self.data.locked_pdus):
            try:
                updated_model = self.find_by_name(pdu_to_unlock.name)
                self.unlock_pdu(updated_model)
            except Exception as e:
                self.logger.warning(f"Error unlocking PDU '{pdu_to_unlock.name}': {e}")
        self.save_to_db()
