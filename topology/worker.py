from utils.util import create_logger
from multiprocessing import Queue, RLock
from topology.topology import Topology
import traceback
from utils.persistency import OSSdb
from nfvo.osm_nbi_util import NbiUtil


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
                topology.create(msg, terraform=msg['terraform'])
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
                topology.add_network(msg)
            elif ops_type == "del_net":
                topology.del_network(msg)
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
