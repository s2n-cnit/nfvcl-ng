from multiprocessing import Process

from nfvcl.blueprints.blue_lcm_beta import LCMWorkersBeta
from nfvcl.utils.log import create_logger
from nfvcl.utils.openstack.openstack_utils import check_openstack_instances
from nfvcl.utils.util import *
from nfvcl.utils import persistency
from nfvcl.topology.topology import topology_lock, build_topology
from nfvcl.topology.topology_worker import TopologyWorker
from nfvcl.nfvo import PNFmanager
from nfvcl.nfvo.osm_nbi_util import get_osm_nbi_utils
from nfvcl.blueprints import LCMWorkers
from nfvcl.subscribe_endpoints.k8s_manager import initialize_k8s_man_subscriber
import signal
import atexit


def handle_exit(*args):
    """
    Handler for exit. Set all managers to be closed, sending them a SIGTERM signal.
    """
    # https://stackoverflow.com/a/322317
    print("Killing all NFVCL processes")
    os.killpg(0, signal.SIGKILL)
    # Main process also get killed, no more code can be run


if __name__ == '__main__':
    # https://stackoverflow.com/a/322317
    os.setpgrp()

# Setup on close handler for the MAIN process.
# It does NOT work with Pycharm stop button! Only with CTRL+C or SIGTERM or SIGINT!!!!
# Pycharm terminates the process such that handle_exit is not called.
atexit.register(handle_exit)
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

nfvcl_config: NFVCLConfigModel = get_nfvcl_config()
logger = create_logger('Main')
nbiUtil = get_osm_nbi_utils()
db = persistency.DB()
# Start process LCM for blueprint 1.0
# old_workers = LCMWorkers(topology_lock)
# # Start process LCM for blueprint 2.0
# workers = LCMWorkersBeta(topology_lock)
# pnf_manager = PNFmanager()

# Start process LCM for topology
topology_worker = TopologyWorker(db, nbiUtil, topology_lock)
topology_worker.start()

# Starting subscribe managers. ADD here all child process start for sub/pub
logger.info("Starting subscribers")
initialize_k8s_man_subscriber(db, nbiUtil, topology_lock)

# ----------------------- HELM REPO --------------------
# setup_helm_repo()


# ----------------------- CHECKS --------------------

def starting_async_checks():
    # Checking that vims are working
    topology = build_topology()
    topo_model = topology.get_model()

    if not (topo_model is None):
        vim_list = topology.get_model().get_vims()
        vim_list=list(filter(lambda x : x.vim_type == "openstack", vim_list))
        err_list = check_openstack_instances(vim_list)
    else:
        logger.warning("Cannot perform initial checks. Topology still need to be initialized.")


Process(target=starting_async_checks, args=()).start()
