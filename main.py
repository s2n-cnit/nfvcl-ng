from utils.util import *
from utils import persistency
from topology import topology_worker, topology_lock, topology_msg_queue
from nfvo import PNFmanager, NbiUtil
from multiprocessing import Process
from blueprints import LCMWorkers
from subscribe_endpoints.k8s_manager import K8sManager
import signal
import atexit

logger = create_logger('Main')
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)
db = persistency.DB()
workers = LCMWorkers(topology_lock)
pnf_manager = PNFmanager()

Process(target=topology_worker, args=(db, nbiUtil, topology_msg_queue, topology_lock)).start()


# Starting subscribe manager, add on_close() in handle_exit when adding a new subscriber to events.
logger.info("Starting subscribers")
k8s_manager: K8sManager = K8sManager(db=db, nbiutil=nbiUtil, lock=topology_lock)
k8s_manager.initialize_k8s_man_subscriber()

# ----------------------- ON CLOSE SECTION --------------------

def handle_exit(*args):
    """
    Handler for exit. Set all managers to be closed, don't close directly them.
    """
    try:
        logger.info("Closing all subscribers endpoints processes")
        k8s_manager.close()
        logger.info("Successfully closed all subscriber endpoints processes")
    except BaseException as exception:
        logger.error("Error while closing subscriber endpoints!!!")
        logger.error(exception)


# Setup on close handler. It does NOT work with Pycharm stop button! Only with CTRL+C or SIGTERM or SIGINT"!!!!
atexit.register(handle_exit)
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)
