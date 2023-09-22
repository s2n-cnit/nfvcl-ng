from models.k8s.topology_k8s_model import K8sModel
from models.network import NetworkModel, RouterModel, PduModel
from models.prometheus.prometheus_model import PrometheusServerModel
from models.topology import TopologyModel
from models.topology.topology_worker_model import TopologyWorkerMessage, TopologyWorkerOperation
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
        raw_msg = queue.get()
        # Debug info
        logger.debug("[topology_worker] new msg received:{}".format(raw_msg))

        # Parsing the message into model
        worker_message = TopologyWorkerMessage.model_validate(raw_msg)
        ops_type: TopologyWorkerOperation = worker_message.ops_type

        # !!! The topology obj is retrieved by the db at any msg to update by possible changes in other threads/processes
        topology = Topology.from_db(db, nbiutil, lock)
        success = True
        # TODO USE switch case
        try:
            # Topology
            if ops_type == TopologyWorkerOperation.ADD_TOPOLOGY:
                topology.create(TopologyModel.model_validate(worker_message.data),
                                terraform=worker_message.optional_data['terraform'])

            elif ops_type == TopologyWorkerOperation.DEL_TOPOLOGY:
                topology.delete(terraform=worker_message.optional_data['terraform'])

            # Vim
            elif ops_type == TopologyWorkerOperation.ADD_VIM:
                topology.add_vim(VimModel.model_validate(worker_message.data),
                                 terraform=worker_message.optional_data['terraform'])

            elif ops_type == TopologyWorkerOperation.UPDATE_VIM:
                topology.update_vim(UpdateVimModel.model_validate(worker_message.data),
                                    terraform=worker_message.optional_data['terraform'])

            elif ops_type == TopologyWorkerOperation.DEL_VIM:
                topology.del_vim(worker_message.data['vim_name'], terraform=worker_message.optional_data['terraform'])
            # Net
            elif ops_type == TopologyWorkerOperation.ADD_NET:
                topology.add_network(NetworkModel.model_validate(worker_message.data),
                                     worker_message.optional_data['terraform'])

            elif ops_type == TopologyWorkerOperation.DEL_NET:
                topology.del_network_by_name(worker_message.data['network_id'],
                                             terraform=worker_message.optional_data['terraform'])

            # Router
            elif ops_type == TopologyWorkerOperation.ADD_ROUTER:
                topology.add_router(RouterModel.model_validate(worker_message.data))

            elif ops_type == TopologyWorkerOperation.DEL_ROUTER:
                topology.del_router(worker_message.data['router_id'])

            # Pdu
            elif ops_type == TopologyWorkerOperation.ADD_PDU:
                topology.add_pdu(PduModel.model_validate(worker_message.data))

            elif ops_type == TopologyWorkerOperation.DEL_PDU:
                topology.del_router(worker_message.data['pdu_id'])

            # K8S
            elif ops_type == TopologyWorkerOperation.ADD_K8S:
                topology.add_k8scluster(K8sModel.model_validate(worker_message.data))

            elif ops_type == TopologyWorkerOperation.DEL_K8S:
                topology.del_k8scluster(worker_message.data['cluster_name'])

            elif ops_type == TopologyWorkerOperation.UPDATE_K8S:
                topology.update_k8scluster(K8sModel.model_validate(worker_message.data))

            # PROMETHEUS
            elif ops_type == TopologyWorkerOperation.ADD_PROM:
                topology.add_prometheus_server(prom_server=PrometheusServerModel.model_validate(worker_message.data))

            elif ops_type == TopologyWorkerOperation.DEL_PROM:
                topology.del_prometheus_server(worker_message.data['prom_srv_id'])

            elif ops_type == TopologyWorkerOperation.UPD_PROM:
                topology.update_prometheus_server(prom_server=PrometheusServerModel.model_validate(worker_message.data))
            # ERROR
            else:
                logger.error('Message not supported: {}'.format(worker_message))
        except Exception:
            logger.error(traceback.format_exc())
            success = False

        finally:
            if worker_message.callback:
                logger.warning("Add here the code for the callback message {} {}".format(ops_type, success))
            # FIXME: pubsub here?
