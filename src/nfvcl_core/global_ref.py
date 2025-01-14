from typing import Optional

from nfvcl_core.config import NFVCLConfigModel

# This file is for global references that are used in the whole project
# It is used to avoid circular imports in the project

nfvcl_config: Optional[NFVCLConfigModel] = None


def get_nfvcl_config() -> NFVCLConfigModel:
    return nfvcl_config
