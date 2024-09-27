from abc import abstractmethod

from nfvcl.blueprints_ng.pdu_configurators.pdu_configurator import PDUConfigurator
from nfvcl.models.pdu.gnb import GNBPDUConfigure


class GNBPDUConfigurator(PDUConfigurator):
    @abstractmethod
    def configure(self, config: GNBPDUConfigure):
        pass
