from typing import Optional

import pytest

from tests.blueprints.blue5g.create_configs import K8S_CLUSTER_5G
from nfvcl_models.blueprint_ng.k8s.k8s_rest_models import K8sCreateModel
from tests.topology.test_topology import TopologyTestContext
from tests.parent_test import NFVCLTestSuite

pytestmark = pytest.mark.integration

class K8STestContext:
    def __init__(self):
        self.k8s_create_model: K8sCreateModel = K8sCreateModel.model_validate(K8S_CLUSTER_5G)
        self.k8s_blue_id: Optional[str] = None

@pytest.fixture(name="context_k8s", scope="session")
def context_k8s(topology_context: TopologyTestContext):
    context_k8s = K8STestContext()
    yield context_k8s
    print("K8S TEARDOWN")

@pytest.mark.dependency(name="test_k8s", depends=["test_topology"], scope="session")
class TestGroupK8s(NFVCLTestSuite):
    @pytest.fixture(autouse=True)
    def _context_k8s(self, context_k8s: K8STestContext):
        self.context_k8s: K8STestContext = context_k8s

    def test_deploy_k8s(self):
        self.context_k8s.k8s_blue_id = self.nfvcl.create_blueprint("k8s", self.context_k8s.k8s_create_model)
