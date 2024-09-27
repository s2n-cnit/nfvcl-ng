from nfvcl.blueprints_ng.lcm.blueprint_manager import get_blueprint_manager
from nfvcl.blueprints_ng.pdu_configurators.types.gnb_pdu_configurator import GNBPDUConfigurator
from nfvcl.models.pdu.gnb import GNBPDUConfigure


class UERANSIMPDUConfigurator(GNBPDUConfigurator):
    def configure(self, config: GNBPDUConfigure):
        get_blueprint_manager().get_worker(self.pdu_model.config["blue_id"]).call_function_sync("configure_gnb", config)
