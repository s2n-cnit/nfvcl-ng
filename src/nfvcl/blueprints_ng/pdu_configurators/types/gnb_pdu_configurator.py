from abc import abstractmethod

from nfvcl.blueprints_ng.pdu_configurators.pdu_configurator import PDUConfigurator
from nfvcl_core_models.pdu.gnb import GNBPDUConfigure, GNBPDUDetach, GNBPDURic


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

    @abstractmethod
    def configure_ric(self, config: GNBPDURic):
        """
        Configure the gNB to the ric.
        Args:
            config: configuration model of the Ric
        """
        pass

    @abstractmethod
    def get_gnb_id(self):
        """
        Configure the gNB to the ric.
        Args:
            config: configuration model of the Ric
        """
        pass
