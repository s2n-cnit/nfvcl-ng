from typing import Optional

import pytest

from blueprints.blue5g.create_configs import K8S_CLUSTER_5G
from nfvcl_core.nfvcl_main import NFVCL
from nfvcl_models.blueprint_ng.k8s.k8s_rest_models import K8sCreateModel
from parent_test import NFVCLTestSuite

class TestContextK8S:
    def __init__(self):
        self.k8s_create_model: K8sCreateModel = K8sCreateModel.model_validate(K8S_CLUSTER_5G)
        self.k8s_blue_id: Optional[str] = None

@pytest.fixture(name="context_k8s", scope="session")
def context_k8s(nfvcl: NFVCL):
    context_k8s = TestContextK8S()
    yield context_k8s
    print("K8S TEARDOWN")
    nfvcl.delete_blueprint(context_k8s.k8s_blue_id)

@pytest.mark.dependency(name="test_k8s", depends=["test_topology"], scope="session")
class TestGroupK8s(NFVCLTestSuite):
    @pytest.fixture(autouse=True)
    def _context_k8s(self, context_k8s: TestContextK8S):
        self.context_k8s: TestContextK8S = context_k8s

    def test_deploy_k8s(self):
        self.context_k8s.k8s_blue_id = self.nfvcl.create_blueprint("k8s", self.context_k8s.k8s_create_model)
