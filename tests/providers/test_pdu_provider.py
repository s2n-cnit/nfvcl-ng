import pytest

from nfvcl_core_models.network.network_models import PduLockType, PduType
from nfvcl_providers.pdu.pdu_provider import PDUProvider, PDUProviderException
from tests.providers.fakes import FakeTopologyManager, SaveSpy, build_pdu


class FakePduManager:
    def get_implementation(self, instance_type: str) -> str:
        return "tests.providers.test_pdu_provider.FakePduConfigurator"


class FakePduConfigurator:
    def __init__(self, pdu):
        self.pdu = pdu


def test_pdu_provider_finds_pdu_by_area_type_instance_and_name():
    pdu = build_pdu(name="gnb1", area=1, instance_type="ueransim")
    provider = PDUProvider(FakeTopologyManager([pdu]), FakePduManager())

    assert provider.find_pdu(1, PduType.GNB, instance_type="ueransim") == pdu
    assert provider.find_pdu(1, PduType.GNB, name="gnb1") == pdu


def test_pdu_provider_raises_when_find_is_ambiguous_or_empty():
    provider = PDUProvider(
        FakeTopologyManager([
            build_pdu(name="gnb1", area=1),
            build_pdu(name="gnb2", area=1),
        ]),
        FakePduManager(),
    )

    with pytest.raises(PDUProviderException):
        provider.find_pdu(1, PduType.GNB)

    with pytest.raises(PDUProviderException):
        provider.find_pdu(99, PduType.GNB)


def test_pdu_provider_locks_and_unlocks_pdu_with_persistence():
    pdu = build_pdu()
    topology_manager = FakeTopologyManager([pdu])
    save = SaveSpy()
    provider = PDUProvider(topology_manager, FakePduManager(), persistence_function=save)

    locked = provider.lock_pdu(pdu, PduLockType.CORE, blueprint_id="blue-a")

    assert locked.locked_list_by[0].blueprint_id == "blue-a"
    assert provider.data.locked_pdus_by_blueprint["blue-a"] == [pdu]
    assert topology_manager.updated_pdus == [pdu]
    assert save.calls == 1

    with pytest.raises(PDUProviderException):
        provider.lock_pdu(pdu, PduLockType.CORE, blueprint_id="blue-b")

    with pytest.raises(PDUProviderException):
        provider.unlock_pdu(pdu, PduLockType.CORE, blueprint_id="blue-b")

    unlocked = provider.unlock_pdu(pdu, PduLockType.CORE, blueprint_id="blue-a")

    assert unlocked.locked_list_by == []
    assert provider.data.locked_pdus_by_blueprint["blue-a"] == []
    assert save.calls == 2


def test_pdu_provider_cleanup_unlocks_pdus_owned_by_blueprint():
    pdu = build_pdu()
    save = SaveSpy()
    provider = PDUProvider(FakeTopologyManager([pdu]), FakePduManager(), persistence_function=save)
    provider.lock_pdu(pdu, PduLockType.GENERIC, blueprint_id="blue-a")

    provider.cleanup_resource_group("blue-a")

    assert pdu.locked_list_by == []
    assert "blue-a" not in provider.data.locked_pdus_by_blueprint
    assert save.calls == 3


def test_pdu_provider_returns_configurator_only_to_lock_owner():
    pdu = build_pdu(instance_type="fake")
    provider = PDUProvider(FakeTopologyManager([pdu]), FakePduManager())
    provider.lock_pdu(pdu, PduLockType.RIC, blueprint_id="blue-a")

    configurator = provider.get_pdu_configurator(pdu, PduLockType.RIC, blueprint_id="blue-a")

    assert isinstance(configurator, FakePduConfigurator)
    assert configurator.pdu == pdu

    with pytest.raises(PDUProviderException):
        provider.get_pdu_configurator(pdu, PduLockType.RIC, blueprint_id="blue-b")
