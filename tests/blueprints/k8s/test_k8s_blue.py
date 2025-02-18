import unittest
from pathlib import Path
from typing import Dict

from nfvcl_core.managers import BlueprintManager
import json

from nfvcl_core.utils.k8s import get_k8s_config_from_file_content
from nfvcl_core.utils.k8s.kube_api_utils import get_pods_for_k8s_namespace
from nfvcl_models.blueprint_ng.k8s.k8s_rest_models import K8sCreateModel

CREATION_FILE_REQUESTS = Path('tests/blueprints/k8s/creation_requests.json')
assert CREATION_FILE_REQUESTS.exists() and CREATION_FILE_REQUESTS.is_file()


class KubernetesBlueTestCase(unittest.TestCase):
    bp_id: str
    blueprint_manager = BlueprintManager()
    details: Dict = []

    def test_001(self):
        """
        Check successful creation for different case of k8s clusters
        """
        json_requests = json.loads(CREATION_FILE_REQUESTS.read_text())
        for i in range(0, len(json_requests)):
            creation_request = json_requests[i]
            creation_model = K8sCreateModel.model_validate(creation_request)
            # Ensure the last one is onboarded in the topology
            if len(json_requests) - i == 1:
                creation_model.topology_onboard = True
            # Create blueprint
            self.__class__.bp_id = self.blueprint_manager.create_blueprint(creation_model, "k8s", True)
            bp_id = self.__class__.bp_id
            # Check if in error state
            self.assertFalse(self.blueprint_manager.get_worker(bp_id).blueprint.base_model.status.error)
            self.assertIsNotNone(bp_id)
            details = self.blueprint_manager.get_blueprint_summary_by_id(bp_id, True)
            self.assertIsNotNone(details)
            self.assertNotEqual(details, "[]")
            # The last one is not deleted
            if not len(json_requests) - i == 1:
                deleted_id = self.blueprint_manager.delete_blueprint(bp_id, True)
                self.assertIsNotNone(deleted_id)

        print("Ended Test_001")

    def test_002(self):
        worker = self.blueprint_manager.get_worker(self.__class__.bp_id)
        master_credential = worker.blueprint.state.master_credentials
        client_config = get_k8s_config_from_file_content(master_credential)
        empty = get_pods_for_k8s_namespace(client_config, "default")
        not_empty = get_pods_for_k8s_namespace(client_config, "kube-system")

        deleted_id = self.blueprint_manager.delete_blueprint(self.__class__.bp_id, True)
        self.assertIsNotNone(deleted_id)
