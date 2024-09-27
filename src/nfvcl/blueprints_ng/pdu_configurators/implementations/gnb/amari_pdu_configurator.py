from nfvcl.blueprints_ng.pdu_configurators.types.gnb_pdu_configurator import GNBPDUConfigurator
from nfvcl.models.pdu.gnb import GNBPDUConfigure


class AmariPDUConfigurator(GNBPDUConfigurator):
    def configure(self, config: GNBPDUConfigure):
        raise NotImplementedError()
