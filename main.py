from multiprocessing import Process

import utils.log
import multiprocessing
from blueprints.blue_lcm_beta import LCMWorkersBeta
from utils.openstack.openstack_utils import check_openstack_instances
from utils.util import *
from utils import persistency
from topology.topology import topology_lock, build_topology
from topology.topology_worker import TopologyWorker
from nfvo import PNFmanager
from nfvo.osm_nbi_util import get_osm_nbi_utils
from blueprints import LCMWorkers
from subscribe_endpoints.k8s_manager import initialize_k8s_man_subscriber
from utils.helm_repository import setup_helm_repo
import signal
import atexit

nfvcl_config: NFVCLConfigModel = get_nfvcl_config()
logger = utils.log.create_logger('Main')
nbiUtil = get_osm_nbi_utils()
db = persistency.DB()
# Start process LCM for blueprint 1.0
old_workers = LCMWorkers(topology_lock)
# Start process LCM for blueprint 2.0
workers = LCMWorkersBeta(topology_lock)
pnf_manager = PNFmanager()

# Start process LCM for topology
topology_worker = TopologyWorker(db, nbiUtil, topology_lock)
topology_worker.start()

# Starting subscribe managers. ADD here all child process start for sub/pub
logger.info("Starting subscribers")
initialize_k8s_man_subscriber(db, nbiUtil, topology_lock)

# ----------------------- HELM REPO --------------------
setup_helm_repo()

# ----------------------- ON CLOSE SECTION --------------------
# Retrieving the list of spawned child (subscribers to nfvcl messages/events, e.g. K8S manager)
spawned_children_list = multiprocessing.active_children()

def handle_exit(*args):
    """
    Handler for exit. Set all managers to be closed, sending them a SIGTERM signal.
    """
    try:
        logger.info("Closing all subscribers endpoints processes")
        for child in spawned_children_list:
            os.kill(child.pid, signal.SIGTERM)
        logger.info("Successfully closed all subscriber endpoints processes")
        os.kill(os.getpid(), signal.SIGTERM)
    except BaseException as err:
        logger.error("Error while closing subscriber endpoints!!!")
        logger.error(err)

# Setup on close handler for the MAIN process.
# It does NOT work with Pycharm stop button! Only with CTRL+C or SIGTERM or SIGINT!!!!
# Pycharm terminates the process such that handle_exit is not called.
atexit.register(handle_exit)
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

# ----------------------- CHECKS --------------------

def starting_async_checks():
    # Checking that vims are working
    topology = build_topology()
    topo_model = topology.get_model()

    if not (topo_model is None):
        vim_list = topology.get_model().get_vims()
        err_list = check_openstack_instances(vim_list)
    else:
        logger.warning("Cannot perform initial checks. Topology still need to be initialized.")

Process(target=starting_async_checks, args=()).start()
