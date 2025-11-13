from nfvcl.blueprints_ng.pdu_configurators.types.gnb_pdu_configurator import GNBPDUConfigurator
from nfvcl_core.managers.getters import get_blueprint_manager
from nfvcl_core_models.pdu.gnb import GNBPDUConfigure


class UERANSIMPDUConfigurator(GNBPDUConfigurator):
    def configure(self, config: GNBPDUConfigure):
        get_blueprint_manager().call_function(self.pdu_model.config["blue_id"], "configure_gnb", config)
