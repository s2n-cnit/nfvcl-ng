from abc import abstractmethod

from nfvcl.blueprints_ng.pdu_configurators.pdu_configurator import PDUConfigurator
from nfvcl.models.blueprint_ng.core5g.common import Create5gModel


class Generic5GConfigurator(PDUConfigurator):
    @abstractmethod
    def configure(self, config: Create5gModel):
        pass
