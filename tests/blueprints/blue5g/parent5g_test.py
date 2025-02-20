import pytest

from blueprints.blue5g.context_5g import TestContext5G
from parent_test import NFVCLTestSuite
from topology.test_topology import TestContextTopology


class NFVCL5GTestSuite(NFVCLTestSuite):
    @pytest.fixture(autouse=True)
    def _topology_context(self, topology_context: TestContextTopology):
        self.topology_context: TestContextTopology = topology_context

    @pytest.fixture(autouse=True)
    def _context_5g(self, context_5g: TestContext5G):
        self.context_5g: TestContext5G = context_5g
