import copy

import pytest

from nfvcl_core.nfvcl_main import NFVCL
from nfvcl_core_models.network import PduModel
from nfvcl_core_models.prometheus.prometheus_model import PrometheusServerModel
from nfvcl_core_models.topology_k8s_model import TopologyK8sModel
from nfvcl_core_models.topology_models import TopologyModel
from nfvcl_core_models.vim import VimModel
from parent_test import NFVCLTestSuite
from topology.models import TOPOLOGY_OK, VIM_TO_ADD1, VIM_TO_ADD2, PDU_TO_ADD, K8S_TO_ADD, PROMETHEUS_TO_ADD


class TestContextTopology:
    def __init__(self):
        self.topology_model = TopologyModel.model_validate(TOPOLOGY_OK)
        self.vim_to_add1_model = VimModel.model_validate(VIM_TO_ADD1)
        self.vim_to_add2_model = VimModel.model_validate(VIM_TO_ADD2)
        self.pdu_model = PduModel.model_validate(PDU_TO_ADD)
        self.kubernetes_model = TopologyK8sModel.model_validate(K8S_TO_ADD)
        self.prometheus_model = PrometheusServerModel.model_validate(PROMETHEUS_TO_ADD)


@pytest.mark.dependency(name="test_topology", depends=["TestInit"], scope="session")
class TestGroupTopology(NFVCLTestSuite):
    def test_delete(self, topology_context: TestContextTopology):
        self.nfvcl.delete_topology()

    def test_get_after_delete(self, topology_context: TestContextTopology):
        with pytest.raises(Exception):
            self.nfvcl.get_topology()

    def test_create(self, topology_context: TestContextTopology):
        self.nfvcl.create_topology(topology_context.topology_model)

    def test_get_after_create(self, topology_context: TestContextTopology):
        assert self.nfvcl.get_topology() == topology_context.topology_model

    # Test VIMs

    def test_get_vim(self, topology_context: TestContextTopology):
        vim = topology_context.topology_model.vims[0]
        assert self.nfvcl.get_vim(vim.name) == vim

    def test_create_vim(self, topology_context: TestContextTopology):
        vim1 = topology_context.vim_to_add1_model
        vim2 = topology_context.vim_to_add2_model

        # Should raise exception because of overlapping areas
        with pytest.raises(Exception):
            self.nfvcl.create_vim(vim1)

        # Should not be present
        with pytest.raises(Exception):
            self.nfvcl.get_vim(vim1.name)

        # Should work
        self.nfvcl.create_vim(vim2)
        assert self.nfvcl.get_vim(vim2.name) == vim2

    def test_update_vim(self, topology_context: TestContextTopology):
        vim = copy.deepcopy(topology_context.vim_to_add2_model)
        vim.areas = [10,11]
        self.nfvcl.update_vim(vim)
        assert self.nfvcl.get_vim(vim.name) == vim

    def test_delete_vim(self, topology_context: TestContextTopology):
        vim = topology_context.vim_to_add2_model
        self.nfvcl.delete_vim(vim.name)
        with pytest.raises(Exception):
            self.nfvcl.get_vim(vim.name)

    # Test PDU

    def test_get_pdus_empty(self, topology_context: TestContextTopology):
        assert self.nfvcl.get_pdus() == []

    def test_create_pdu(self, topology_context: TestContextTopology):
        self.nfvcl.create_pdu(topology_context.pdu_model)
        assert self.nfvcl.get_pdus() == [topology_context.pdu_model]

    def test_get_pdu(self, topology_context: TestContextTopology):
        assert self.nfvcl.get_pdu(topology_context.pdu_model.name) == topology_context.pdu_model

    def test_delete_pdu(self, topology_context: TestContextTopology):
        self.nfvcl.delete_pdu(topology_context.pdu_model.name)
        assert self.nfvcl.get_pdus() == []

        with pytest.raises(Exception):
            self.nfvcl.delete_pdu("non-existing")

    def test_get_kubernetes_empty(self, topology_context: TestContextTopology):
        assert self.nfvcl.get_kubernetes_list() == []

    def test_create_kubernetes(self, topology_context: TestContextTopology):
        self.nfvcl.create_kubernetes_external(topology_context.kubernetes_model)
        assert self.nfvcl.get_kubernetes_list() == [topology_context.kubernetes_model]

    def test_get_kubernetes(self, topology_context: TestContextTopology):
        assert self.nfvcl.get_kubernetes(topology_context.kubernetes_model.name) == topology_context.kubernetes_model

    def test_delete_kubernetes(self, topology_context: TestContextTopology):
        self.nfvcl.delete_kubernetes(topology_context.kubernetes_model.name)

        with pytest.raises(Exception):
            self.nfvcl.delete_kubernetes("non-existing")

    def test_get_prometheus_empty(self, topology_context: TestContextTopology):
        assert self.nfvcl.get_prometheus_list() == []

    def test_create_prometheus(self, topology_context: TestContextTopology):
        self.nfvcl.create_prometheus(topology_context.prometheus_model)
        assert self.nfvcl.get_prometheus_list() == [topology_context.prometheus_model]

    def test_get_prometheus(self, topology_context: TestContextTopology):
        assert self.nfvcl.get_prometheus(topology_context.prometheus_model.id) == topology_context.prometheus_model

    def test_update_prometheus(self, topology_context: TestContextTopology):
        prometheus = copy.deepcopy(topology_context.prometheus_model)
        prometheus.password = "newpasswd"
        self.nfvcl.update_prometheus(prometheus)
        assert self.nfvcl.get_prometheus(prometheus.id).password == "newpasswd"

    def test_delete_prometheus(self, topology_context: TestContextTopology):
        # Should fail because there are configured targets
        with pytest.raises(ValueError):
            self.nfvcl.delete_prometheus(topology_context.prometheus_model.id)

        # Delete targets
        prometheus = copy.deepcopy(topology_context.prometheus_model)
        prometheus.targets = []
        self.nfvcl.update_prometheus(prometheus)

        # Try to delete again
        self.nfvcl.delete_prometheus(topology_context.prometheus_model.id)

        with pytest.raises(Exception):
            self.nfvcl.delete_prometheus("non-existing")

    def test_back_to_original(self, topology_context: TestContextTopology):
        assert self.nfvcl.get_topology() == topology_context.topology_model
