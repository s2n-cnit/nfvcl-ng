from nfvcl_core.nfvcl_main import configure_injection
from nfvcl_core_models.config import load_nfvcl_config

configure_injection(load_nfvcl_config("tests/config.yaml"))
