from nfvcl.blueprints_ng.pdu_configurators.implementations.gnb.amari_pdu_configurator import AmariPDUConfigurator

from nfvcl.blueprints_ng.pdu_configurators.implementations.gnb.liteon_aio_pdu_configurator import LiteonAIOPDUConfigurator

from nfvcl.blueprints_ng.pdu_configurators.implementations.generic_linux_pdu_configurator import GenericLinuxPDUConfigurator
from nfvcl.blueprints_ng.pdu_configurators.implementations.gnb.ueransim_pdu_configurator import UERANSIMPDUConfigurator

from nfvcl.blueprints_ng.lcm.pdu_manager import get_pdu_manager

pdu_manager = get_pdu_manager()

pdu_manager.register_implementation("UERANSIM", UERANSIMPDUConfigurator.get_class_path())
pdu_manager.register_implementation("GENERIC", GenericLinuxPDUConfigurator.get_class_path())
pdu_manager.register_implementation("LiteONAIO", LiteonAIOPDUConfigurator.get_class_path())
pdu_manager.register_implementation("AmarisoftGNB", AmariPDUConfigurator.get_class_path())
