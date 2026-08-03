import pytest

from tests.blueprints.blue5g.context_5g import FiveGTestContext
from tests.parent_test import NFVCLTestSuite
from tests.topology.test_topology import TopologyTestContext


class NFVCL5GTestSuite(NFVCLTestSuite):
    @pytest.fixture(autouse=True)
    def _topology_context(self, topology_context: TopologyTestContext):
        self.topology_context: TopologyTestContext = topology_context

    @pytest.fixture(autouse=True)
    def _context_5g(self, context_5g: FiveGTestContext):
        self.context_5g: FiveGTestContext = context_5g
