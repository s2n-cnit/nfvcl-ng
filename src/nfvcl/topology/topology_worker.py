import traceback
from multiprocessing import Queue, RLock
from threading import Thread

from nfvcl.models.k8s.topology_k8s_model import TopologyK8sModel
from nfvcl.models.network import NetworkModel, RouterModel, PduModel
from nfvcl.models.prometheus.prometheus_model import PrometheusServerModel
from nfvcl.models.topology import TopologyModel
from nfvcl.models.topology.topology_worker_model import TopologyWorkerMessage, TopologyWorkerOperation
from nfvcl.models.vim import UpdateVimModel, VimModel
from nfvcl.topology.topology import Topology, build_topology
from nfvcl.utils.log import create_logger

logger = create_logger('Topology Worker')
topology_msg_queue: Queue = Queue()


class TopologyWorker:
    topology_msg_queue_local: Queue
    topology_lock: RLock

    def __init__(self, topology_lock):
        super().__init__()
        self.topology_lock = topology_lock
        self.topology_msg_queue_local = topology_msg_queue

    def start(self):
        """
        Start the topology worker in a separate Thread
        """
        # Do not change with Process since it clones all data and works on different variables
        thread = Thread(target=self.listen, args=())
        thread.daemon = True
        thread.start()

    def listen(self):
        logger.debug('Started listening')
        while True:
            raw_msg = self.topology_msg_queue_local.get()
            # Debug info
            logger.debug("New msg received:{}".format(raw_msg))

            # Parsing the message into the model
            worker_message = TopologyWorkerMessage.model_validate(raw_msg)
            ops_type: TopologyWorkerOperation = worker_message.ops_type

            # !!! The topology obj is retrieved by the db at any msg to update by possible changes in other threads/processes
            topology = build_topology()
            success = True
            try:
                self.start_operation(ops_type, worker_message, topology)

            except Exception:
                logger.error(traceback.format_exc())
                success = False

            finally:
                if worker_message.callback:
                    logger.warning("Add here the code for the callback message {} {}".format(ops_type, success))
                # FIXME: pubsub here?

    def start_operation(self, ops_type: TopologyWorkerOperation, worker_message: TopologyWorkerMessage, topology: Topology):

        match ops_type:
            # TOPOLOGY
            case TopologyWorkerOperation.ADD_TOPOLOGY:
                topology.create(TopologyModel.model_validate(worker_message.data), terraform=worker_message.optional_data['terraform'])

            case TopologyWorkerOperation.DEL_TOPOLOGY:
                topology.delete(terraform=worker_message.optional_data['terraform'])

            # VIM OPERATION
            case TopologyWorkerOperation.ADD_VIM:
                topology.add_vim(VimModel.model_validate(worker_message.data), terraform=worker_message.optional_data['terraform'])

            case TopologyWorkerOperation.UPDATE_VIM:
                topology.update_vim(UpdateVimModel.model_validate(worker_message.data), terraform=worker_message.optional_data['terraform'])

            case TopologyWorkerOperation.DEL_VIM:
                topology.del_vim(worker_message.data['vim_name'], terraform=worker_message.optional_data['terraform'])

            # NETWORK OPERATION
            case TopologyWorkerOperation.ADD_NET:
                topology.add_network(NetworkModel.model_validate(worker_message.data), worker_message.optional_data['terraform'])

            case TopologyWorkerOperation.DEL_NET:
                topology.del_network_by_name(worker_message.data['network_id'], terraform=worker_message.optional_data['terraform'])

            # Router
            case TopologyWorkerOperation.ADD_ROUTER:
                topology.add_router(RouterModel.model_validate(worker_message.data))

            case TopologyWorkerOperation.DEL_ROUTER:
                topology.del_router(worker_message.data['router_id'])

            # Pdu
            case TopologyWorkerOperation.ADD_PDU:
                pdu_model = PduModel.model_validate(worker_message.data)
                topology.add_pdu(pdu_model, pdu_model.nfvo_onboarded)

            case TopologyWorkerOperation.DEL_PDU:
                topology.del_router(worker_message.data['pdu_id'])

            # K8S
            case TopologyWorkerOperation.ADD_K8S:
                topology.add_k8scluster(TopologyK8sModel.model_validate(worker_message.data))

            case TopologyWorkerOperation.DEL_K8S:
                topology.del_k8scluster(worker_message.data['cluster_name'])

            case TopologyWorkerOperation.UPDATE_K8S:
                topology.update_k8scluster(TopologyK8sModel.model_validate(worker_message.data))

            # PROMETHEUS
            case TopologyWorkerOperation.ADD_PROM:
                topology.add_prometheus_server(prom_server=PrometheusServerModel.model_validate(worker_message.data))

            case TopologyWorkerOperation.DEL_PROM:
                topology.del_prometheus_server(worker_message.data['prom_srv_id'])

            case TopologyWorkerOperation.UPD_PROM:
                topology.update_prometheus_server(prom_server=PrometheusServerModel.model_validate(worker_message.data))
            # ERROR
            case _:
                logger.error('Message not supported: {}'.format(worker_message))
