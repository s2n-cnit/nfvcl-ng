from typing import Optional, List

import pytest

from blueprints.blue5g.create_configs import CORE_5G, UERANSIM1, UERANSIM2
from blueprints.blue5g.models.ueransim import UeransimGNB
from blueprints.ueransim_utils import UeransimSSH
from nfvcl.blueprints_ng.modules import UeransimBlueprintNG
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g import Generic5GBlueprintNG
from nfvcl_core.nfvcl_main import NFVCL
from nfvcl_models.blueprint_ng.core5g.common import Create5gModel
from nfvcl_models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestInstance
from topology.test_topology import TestContextTopology


class TestContext5G:
    def __init__(self):
        self.ueransim1_create_model: UeransimBlueprintRequestInstance = UeransimBlueprintRequestInstance.model_validate(UERANSIM1)
        self.ueransim2_create_model: UeransimBlueprintRequestInstance = UeransimBlueprintRequestInstance.model_validate(UERANSIM2)
        self.core_5g_create_model: Create5gModel = Create5gModel.model_validate(CORE_5G)
        self.ueransim1_bp_id = None
        self.ueransim2_bp_id = None
        self.ueransim1: Optional[UeransimBlueprintNG] = None
        self.ueransim2: Optional[UeransimBlueprintNG] = None


        self.ueransim1_radio_list: List[UeransimGNB] = []


        self.core_bp_id = None
        self.core: Optional[Generic5GBlueprintNG] = None

        self.ueransim_ue_ssh: Optional[UeransimSSH] = None
        self.ueransim_gnb_ssh: Optional[UeransimSSH] = None


@pytest.fixture(name="context_5g", scope="session")
def context_5g_fixture(nfvcl: NFVCL, topology_context: TestContextTopology):
    context_5g = TestContext5G()
    yield context_5g
    # Teardown
    print("5G TEARDOWN")
    nfvcl.delete_blueprint(context_5g.core_bp_id)
    nfvcl.delete_blueprint(context_5g.ueransim1_bp_id)
