from models.network import NetworkModel
from models.topology import TopologyModel
from utils.util import create_logger
from multiprocessing import Queue, RLock
from topology import Topology
import traceback
from utils.persistency import OSSdb
from nfvo import NbiUtil


logger = create_logger('Topology Worker')


def topology_worker(db: OSSdb, nbiutil: NbiUtil, queue: Queue, lock: RLock):
    logger.debug('initialized')
    while True:
        msg = queue.get()
        logger.info("[topology_worker] new msg received:{}".format(msg))
        # the topology obj is retrieved by the db at any msg to update by possible changes in other threads/processes
        topology = Topology.from_db(db, nbiutil, lock)
        ops_type = msg["ops_type"]
        msg.pop("ops_type")
        success = True
        try:
            # topology
            if ops_type == "add_topology":
                topology.create(TopologyModel.parse_obj(msg), terraform=msg['terraform'])
            elif ops_type == "del_topology":
                topology.delete(terraform=msg['terraform'])
            # vim
            elif ops_type == "add_vim":
                topology.add_vim(msg, terraform=msg['terraform'])
            elif ops_type == "update_vim":
                topology.update_vim(msg, terraform=msg['terraform'])
            elif ops_type == "del_vim":
                topology.del_vim(msg, terraform=msg['terraform'])
            # net
            elif ops_type == "add_net":
                topology.add_network(NetworkModel.parse_obj(msg))
            elif ops_type == "del_net":
                topology.del_network(NetworkModel.parse_obj(msg))
            # router
            elif ops_type == "add_router":
                topology.add_router(msg)
            elif ops_type == "del_router":
                topology.del_router(msg)
            # pdu
            elif ops_type == "add_pdu":
                topology.add_pdu(msg)
            elif ops_type == "del_pdu":
                topology.del_pdu(msg)
            elif ops_type == "add_k8s":
                topology.add_k8scluster(msg)
            elif ops_type == "del_k8s":
                # Since K8s instance is taken by database, as stated in K8sModel, the field is called "name"
                cluster_id = msg.pop("name")
                topology.del_k8scluster(cluster_id)
            elif ops_type == "update_k8s":
                cluster_id = msg.pop("cluster_id")
                topology.update_k8scluster(name=cluster_id, data=msg)
            else:
                logger.error('message not supported: {}'.format(msg))
        except Exception:
            logger.error(traceback.format_exc())
            success = False
        else:
            topology.save_topology()

        finally:
            if 'callback' in msg and msg['callback']:
                logger.warn("add here the code for the callback message {} {}".format(ops_type, success))
            # FIXME: pubsub here?
