import pytest

from nfvcl_core.nfvcl_main import NFVCL


class NFVCLTestSuite:
    @pytest.fixture(autouse=True)
    def _nfvcl(self, nfvcl: NFVCL):
        self.nfvcl: NFVCL = nfvcl
