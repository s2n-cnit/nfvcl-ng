from nfvcl_core.managers import PDUManager

from nfvcl.blueprints_ng.pdu_configurators.implementations.gnb.amari_pdu_configurator import AmariPDUConfigurator

from nfvcl.blueprints_ng.pdu_configurators.implementations.core_5g.athonet.athonet_core_pdu_configurator import AthonetCorePDUConfigurator
from nfvcl.blueprints_ng.pdu_configurators.implementations.core_5g.athonet.athonet_upf_pdu_configurator import AthonetUPFPDUConfigurator
from nfvcl.blueprints_ng.pdu_configurators.implementations.gnb.liteon_aio_pdu_configurator import LiteonAIOPDUConfigurator

from nfvcl.blueprints_ng.pdu_configurators.implementations.generic_linux_pdu_configurator import GenericLinuxPDUConfigurator
from nfvcl.blueprints_ng.pdu_configurators.implementations.gnb.ueransim_pdu_configurator import UERANSIMPDUConfigurator


def register_pdu_implementations(pdu_manager: PDUManager):
    pdu_manager.register_implementation("UERANSIM", UERANSIMPDUConfigurator.get_class_path())
    pdu_manager.register_implementation("GENERIC", GenericLinuxPDUConfigurator.get_class_path())
    pdu_manager.register_implementation("LiteONAIO", LiteonAIOPDUConfigurator.get_class_path())
    pdu_manager.register_implementation("AthonetCore", AthonetCorePDUConfigurator.get_class_path())
    pdu_manager.register_implementation("AthonetUPF", AthonetUPFPDUConfigurator.get_class_path())
    pdu_manager.register_implementation("AmarisoftGNB", AmariPDUConfigurator.get_class_path())
