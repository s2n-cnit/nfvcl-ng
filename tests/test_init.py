import pytest

from tests.parent_test import NFVCLTestSuite

pytestmark = pytest.mark.integration

@pytest.mark.dependency(name="TestInit", scope="session")
class TestInit(NFVCLTestSuite):
    def test_init(self):
        # We don't need to do anything here because the NFVCL instance is created in the fixture
        assert self.nfvcl is not None

    def test_plugins_init(self):
        assert len(self.nfvcl.plugins) == 1
