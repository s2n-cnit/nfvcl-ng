import unittest
from pathlib import Path
from typing import Dict
from nfvcl.blueprints_ng.lcm.blueprint_manager import BlueprintManager
from nfvcl.models.blueprint_ng.k8s.k8s_rest_models import K8sCreateModel
import json

CREATION_FILE_REQUESTS = Path('tests/blueprints/k8s/creation_requests.json')
assert CREATION_FILE_REQUESTS.exists() and CREATION_FILE_REQUESTS.is_file()


class KubernetesBlueTestCase(unittest.TestCase):
    bp_id: str
    blueprint_manager = BlueprintManager()
    details: Dict = []

    def test_001(self):
        """
        Check successful creation
        Returns:

        """
        json_requests = json.loads(CREATION_FILE_REQUESTS.read_text())
        for creation_request in json_requests:
            creation_model = K8sCreateModel.model_validate(creation_request)
            blue_id = self.blueprint_manager.create_blueprint(creation_model, "k8s", True)
            self.assertIsNotNone(blue_id)
            details = self.blueprint_manager.get_blueprint_summary_by_id(blue_id, True)
            self.assertIsNotNone(details)
            self.assertNotEquals(details, "[]")
            deleted_id = self.blueprint_manager.delete_blueprint(blue_id, True)
            self.assertIsNotNone(deleted_id)

        print("Ended Test_001")


