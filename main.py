from utils.util import *
from utils import persistency
from topology import topology_worker, topology_lock, topology_msg_queue
from nfvo import PNFmanager, NbiUtil
from multiprocessing import Process
from blueprints import LCMWorkers
from subscribe_endpoints.k8s_manager import K8sManager


logger = create_logger('Main')
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)
db = persistency.DB()
workers = LCMWorkers(topology_lock)
pnf_manager = PNFmanager()

Process(target=topology_worker, args=(db, nbiUtil, topology_msg_queue, topology_lock)).start()

logger.info("Starting subscribers")
k8s_manager: K8sManager = K8sManager(db=db, nbiutil=nbiUtil, lock=topology_lock).initialize_k8s_man_subscriber()

# !!!
# For FastAPI and routers instantiation look in the nfvcl.py file!
