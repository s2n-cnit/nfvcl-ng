from abc import abstractmethod

from nfvcl.blueprints_ng.pdu_configurators.pdu_configurator import PDUConfigurator
from nfvcl_core_models.pdu.gnb import GNBPDUConfigure, GNBPDUDetach


class GNBPDUConfigurator(PDUConfigurator):
    @abstractmethod
    def configure(self, config: GNBPDUConfigure):
        """
        Attach the gNB to the core.
        Args:
            config: configuration model of the gNB
        """
        pass

    @abstractmethod
    def detach(self, config: GNBPDUDetach):
        """
        Detach the gNB from the core.
        Args:
            config: configuration model of the gNB
        """
        pass
