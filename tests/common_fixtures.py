import pytest

from nfvcl_core.managers.getters import get_persistence_manager
from nfvcl_core.nfvcl_main import NFVCL
from nfvcl_core.nfvcl_main import configure_injection
from nfvcl_core_models.config import load_nfvcl_config
from tests.topology.test_topology import TopologyTestContext


@pytest.fixture(name="nfvcl", scope="session")
def nfvcl():
    print("Creating NFVCL instance")
    configure_injection(load_nfvcl_config("tests/config.yaml"))
    nfvcl = NFVCL()
    yield nfvcl
    print("NFVCL TEARDOWN")
    get_persistence_manager().mongo_client.drop_database("nfvcl_test")


@pytest.fixture(name="topology_context", scope="session")
def topology_context(nfvcl: NFVCL):
    print("Creating TOPOLOGY")
    topology_context = TopologyTestContext()
    yield topology_context
    print("TOPOLOGY TEARDOWN")
    nfvcl.delete_topology()
