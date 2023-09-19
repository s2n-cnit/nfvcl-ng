from models.k8s.topology_k8s_model import K8sModel
from models.network import NetworkModel, RouterModel, PduModel
from models.prometheus.prometheus_model import PrometheusServerModel
from models.topology import TopologyModel
from models.vim import UpdateVimModel, VimModel
from utils.log import create_logger
from multiprocessing import Queue, RLock
from topology.topology import Topology
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
                topology.create(TopologyModel.model_validate(msg), terraform=msg['terraform'])
            elif ops_type == "del_topology":
                topology.delete(terraform=msg['terraform'])
            # vim
            elif ops_type == "add_vim":
                topology.add_vim(VimModel.model_validate(msg), terraform=msg['terraform'])
            elif ops_type == "update_vim":
                topology.update_vim(UpdateVimModel.model_validate(msg), terraform=msg['terraform'])
            elif ops_type == "del_vim":
                topology.del_vim(msg['vim_name'], terraform=msg['terraform'])
            # net
            elif ops_type == "add_net":
                topology.add_network(NetworkModel.model_validate(msg))
            elif ops_type == "del_net":
                topology.del_network(NetworkModel.model_validate(msg))
            # router
            elif ops_type == "add_router":
                topology.add_router(RouterModel.model_validate(msg))
            elif ops_type == "del_router":
                topology.del_router(msg.pop("router_id"))
            # pdu
            elif ops_type == "add_pdu":
                topology.add_pdu(PduModel.model_validate(msg))
            elif ops_type == "del_pdu":
                topology.del_pdu(msg)
            elif ops_type == "add_k8s":
                topology.add_k8scluster(K8sModel.model_validate(msg))
            elif ops_type == "del_k8s":
                # Since K8s instance is taken by database, as stated in K8sModel, the field is called "name"
                cluster_id = msg.pop("name")
                topology.del_k8scluster(cluster_id)
            elif ops_type == "update_k8s":
                topology.update_k8scluster(K8sModel.model_validate(msg))
            elif ops_type == "add_prom":
                topology.add_prometheus_server(prom_server=PrometheusServerModel.model_validate(msg))
            elif ops_type == "del_prom":
                topology.del_prometheus_server(msg['id'])
            elif ops_type == "upd_prom":
                topology.update_prometheus_server(prom_server=PrometheusServerModel.model_validate(msg))
            else:
                logger.error('message not supported: {}'.format(msg))
        except Exception:
            logger.error(traceback.format_exc())
            success = False

        finally:
            if 'callback' in msg and msg['callback']:
                logger.warning("add here the code for the callback message {} {}".format(ops_type, success))
            # FIXME: pubsub here?
