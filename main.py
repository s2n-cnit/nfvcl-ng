import utils.log
import multiprocessing
from blueprints.blue_lcm_beta import LCMWorkersBeta
from utils.util import *
from utils import persistency
from topology.topology import topology_lock, topology_msg_queue
from topology.worker import topology_worker
from nfvo import PNFmanager
from nfvo.osm_nbi_util import get_osm_nbi_utils
from multiprocessing import Process
from blueprints import LCMWorkers
from subscribe_endpoints.k8s_manager import initialize_k8s_man_subscriber
import signal
import atexit

nfvcl_config: NFVCLConfigModel = get_nfvcl_config()
logger = utils.log.create_logger('Main')
nbiUtil = get_osm_nbi_utils()
db = persistency.DB()
old_workers = LCMWorkers(topology_lock)
workers = LCMWorkersBeta(topology_lock)
pnf_manager = PNFmanager()

Process(target=topology_worker, args=(db, nbiUtil, topology_msg_queue, topology_lock)).start()

# Starting subscribe managers. ADD here all child process start for sub/pub
logger.info("Starting subscribers")
initialize_k8s_man_subscriber(db, nbiUtil, topology_lock)

# ----------------------- ON CLOSE SECTION --------------------
# Retrieving the list of spawned child (subscribers to nfvcl messages/events, e.g. K8S manager)
spawned_children_list = multiprocessing.active_children()


def handle_exit(*args):
    """
    Handler for exit. Set all managers to be closed sending them a SIGTERM signal.
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


# Setup on close handler for MAIN process.
# It does NOT work with Pycharm stop button! Only with CTRL+C or SIGTERM or SIGINT!!!!
# Pycharm terminate the process such that handle_exit is not called.
atexit.register(handle_exit)
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)
