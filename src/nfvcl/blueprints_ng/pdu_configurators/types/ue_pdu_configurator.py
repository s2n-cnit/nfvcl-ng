from abc import abstractmethod

from nfvcl.blueprints_ng.pdu_configurators.pdu_configurator import PDUConfigurator
from nfvcl_core_models.pdu.ue import UEPDUConfigure


class GenericUEConfigurator(PDUConfigurator):
    @abstractmethod
    def configure(self, config: UEPDUConfigure):
        pass

    @abstractmethod
    def cleanup(self):
        pass

    @abstractmethod
    def run_experiment(self):
        pass
