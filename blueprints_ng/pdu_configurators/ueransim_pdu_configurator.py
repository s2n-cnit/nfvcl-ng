from typing import Any

from rest_endpoints.blue_ng_router import get_blueprint_manager

from blueprints_ng.pdu_configurators.pdu_configurator import PDUConfigurator
from models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestConfigureGNB
from models.network import PduModel


class UERANSIMPDUConfigurator(PDUConfigurator):
    def __init__(self, pdu_model: PduModel):
        super().__init__()
        self.pdu_model = pdu_model

    def configure(self, config: UeransimBlueprintRequestConfigureGNB):
        get_blueprint_manager().get_worker(self.pdu_model.config["blue_id"]).call_function_sync("configure_gnb", config)

    def get_n3_info(self):
        return get_blueprint_manager().get_worker(self.pdu_model.config["blue_id"]).call_function_sync("get_n3_info", self.pdu_model.area)
