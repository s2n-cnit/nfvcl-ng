from pathlib import Path

from nfvcl.models.config_model import NFVCLConfigModel
from nfvcl.utils.log import create_logger
from nfvcl.utils.util import get_nfvcl_config


def check_folders():
    """
    Creates empty folders not pushed on GitHub, if not already present.
    """
    Path("helm_charts/charts/").mkdir(parents=True, exist_ok=True)
    Path("day2_files").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)

check_folders()
# Main file to run NFVCL
from logging import Logger
import uvicorn
import sys

logger: Logger
PY_MIN_MAJOR = 3
PY_MIN_MINOR = 11

def check_ip() -> NFVCLConfigModel:
    """
    Checks that an IP has been configured for the NFVCL
    Returns:
         The configuration if the IP is configured, exit otherwise
    """
    nfvcl_config = get_nfvcl_config()
    if nfvcl_config.nfvcl.ip == "":
        logger.error("The IP of NFVCL has not been configured")
        exit(-1)
    return nfvcl_config


def check_py_version():
    """
    Checks that the python version is equal or grater that the required one
    """
    v_info = sys.version_info
    if v_info.major < PY_MIN_MAJOR or v_info.minor < PY_MIN_MINOR:
        logger.error(f"The version of Python must be greater then {PY_MIN_MAJOR}.{PY_MIN_MINOR}. "
                     f"You are using the {sys.version}")
        exit(-1)


if __name__ == "__main__":
    # Logger must be created after folders!!!
    logger = create_logger("RUN")
    check_py_version()
    nfvcl_conf: NFVCLConfigModel = check_ip()
    if nfvcl_conf is not None:
        # Run database migrations
        from nfvcl.utils.db_migration import start_migrations
        start_migrations()

        # Load the app only if pre-configuration is OK.
        from nfvcl.nnfvcl import app
        uvicorn.run(app, host=nfvcl_conf.nfvcl.ip, port=nfvcl_conf.nfvcl.port)
