import pytest

from nfvcl_core.managers import get_persistence_manager
from nfvcl_core.nfvcl_main import NFVCL
from topology.test_topology import TestContextTopology


@pytest.fixture(name="nfvcl", scope="session")
def nfvcl():
    print("Creating NFVCL instance")
    nfvcl = NFVCL()
    yield nfvcl
    print("NFVCL TEARDOWN")
    get_persistence_manager().mongo_client.drop_database("nfvcl_test")


@pytest.fixture(name="topology_context", scope="session")
def topology_context(nfvcl: NFVCL):
    print("Creating TOPOLOGY")
    topology_context = TestContextTopology()
    yield topology_context
    print("TOPOLOGY TEARDOWN")
    nfvcl.delete_topology()
