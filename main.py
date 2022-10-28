from utils.util import *
from blueprints.blue_lcm import LCMWorkers
from nfvo.pnf_manager import PNFmanager
from nfvo.osm_nbi_util import NbiUtil
from multiprocessing import Process
from utils import persistency
from topology.worker import topology_worker
from topology.topology import topology_lock, topology_msg_queue


logger = create_logger('Main')
nbiUtil = NbiUtil(username=osm_user, password=osm_passwd, project=osm_proj, osm_ip=osm_ip, osm_port=osm_port)
db = persistency.db()
workers = LCMWorkers(topology_lock)
pnf_manager = PNFmanager()

Process(target=topology_worker, args=(db, nbiUtil, topology_msg_queue, topology_lock)).start()
# topology = Topology.from_db(db=db, nbiutil=nbiUtil)
