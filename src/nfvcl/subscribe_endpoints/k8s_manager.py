import atexit
import json
import os
import signal
import threading
import traceback
from multiprocessing import Process, RLock
from typing import List

import redis
import yaml
from kubernetes.utils import FailToCreateError
from pydantic import ValidationError
from redis.client import PubSub
from verboselogs import VerboseLogger

from nfvcl.models.k8s.plugin_k8s_model import K8sPluginsToInstall, K8sPluginAdditionalData, K8sOperationType, K8sLoadBalancerPoolArea
from nfvcl.models.k8s.topology_k8s_model import K8sModelManagement, TopologyK8sModel
from nfvcl.topology.topology import Topology
from nfvcl.utils.k8s import get_k8s_config_from_file_content, apply_def_to_cluster, get_k8s_cidr_info
from nfvcl.utils.k8s.helm_plugin_manager import HelmPluginManager
from nfvcl.utils.log import create_logger
from nfvcl.utils.redis_utils.redis_manager import get_redis_instance
from nfvcl.utils.redis_utils.topic_list import K8S_MANAGEMENT_TOPIC


class K8sManager:
    redis_cli: redis.Redis = get_redis_instance()
    subscriber: PubSub = redis_cli.pubsub()
    logger: VerboseLogger
    lock: RLock
    stop: bool

    def __init__(self, lock: RLock):
        """
        Initialize the object and start logger + redis client.
        """
        self.lock = lock
        self.stop = False
        self.locker = threading.RLock()

        self.redis_cli = get_redis_instance()
        self.subscriber = self.redis_cli.pubsub()
        self.logger = create_logger(K8S_MANAGEMENT_TOPIC)

        self.subscriber.subscribe(K8S_MANAGEMENT_TOPIC)


    def is_closed(self) -> bool:
        """
        Check is this manager is closed. THREAD SAFE
        Returns:
            True if closed
        """
        self.locker.acquire()
        is_stopped = self.stop
        self.locker.release()
        return is_stopped

    def close(self, *args):
        """
        Close this manager. THREAD SAFE
        """
        self.logger.debug("Closing K8S manager...")
        self.locker.acquire()
        self.stop = True
        self.locker.release()
        self.logger.debug("Killing K8S manager...")
        os.kill(os.getpid(), signal.SIGKILL)

    def get_k8s_cluster_by_id(self, cluster_id: str) -> TopologyK8sModel:
        """
        Get the k8s cluster from the topology. This method could be duplicated but in this case handle HTTP exceptions
        that give API user an idea of what is going wrong.

        Args:

            cluster_id: the cluster ID that identify a k8s cluster in the topology.

        Returns:

            The matching k8s cluster or Throw ValueError if NOT found.
        """
        topology = Topology.from_db(self.lock)
        k8s_clusters: List[TopologyK8sModel] = topology.get_k8s_clusters()
        match = next((x for x in k8s_clusters if x.name == cluster_id), None)

        if match:
            return match
        else:
            msg_err = "K8s cluster {} not found".format(cluster_id)
            raise ValueError(msg_err)

    def listen_to_k8s_management(self):
        """
        This function is continuously listening for new message on the K8S_MANAGEMENT_TOPIC.

        When a new message comes from the redis subscription
        """
        # Alerting if there are no subscriptions
        if(len(self.subscriber.channels)) <= 0:
            self.logger.warning("There are NO active subscriptions to events!!!")

        for message in self.subscriber.listen():
            # If stop the for loop is exited and the process die
            if self.is_closed():
                break
            try:
                self._delegate_operation(message)
            except Exception as exct:
                self.logger.error("Error while executing requested operation: {}".format(message))
                self.logger.error(exct)
                traceback.print_exc()

    def _delegate_operation(self, message: dict):
        """
        The operation is delegated to the correct function. It looks for the operation type.

        Args:
            message: the received message
        """
        # TODO replace if/elif chain with 'match' for python>3.10
        data = message['data']
        if message['type'] == 'subscribe':
            # Subscription confirmation
            self.logger.info("Successfully subscribed to topic: {}".format(K8S_MANAGEMENT_TOPIC))
        elif message['type'] == 'unsubscribe':
            # Unsubscription confirmation
            self.logger.info("Successfully unsubscribed from topic: {}".format(K8S_MANAGEMENT_TOPIC))
        elif message['type'] == 'message':
            # --- Parsing the message in the model for k8s management ---
            try:
                management_model: K8sModelManagement = K8sModelManagement.model_validate(json.loads(data)['data'])
            except ValidationError as val_err:
                msg_err = "Received model is impossible to validate."
                self.logger.error(msg_err)
                raise val_err

            self.logger.info("Received operation {}. Starting processing the request...".format(management_model.k8s_ops))
            if management_model.k8s_ops == K8sOperationType.INSTALL_PLUGIN:
                self.install_plugins(management_model.cluster_id,
                                     K8sPluginsToInstall.model_validate(json.loads(management_model.data)))
            elif management_model.k8s_ops == K8sOperationType.APPLY_YAML:
                self.apply_to_k8s(management_model.cluster_id, management_model.data)
            else:
                self.logger.warning("Operation {} not supported".format(management_model.k8s_ops))
        else:
            msg_err = "Redis message type not recognized."
            self.logger.error(msg_err)
            raise ValidationError(msg_err)

    def install_plugins(self, cluster_id: str, plug_to_install_list: K8sPluginsToInstall):
        """
        Install a plugin to a target k8s cluster

        Args:
            cluster_id: The target k8s cluster

            plug_to_install_list: The list of enabled plugins to be installed together with data to fill plugin file
            templates.
        """
        # Getting k8s cluster from topology
        cluster = self.get_k8s_cluster_by_id(cluster_id)

        lb_pool: K8sLoadBalancerPoolArea = plug_to_install_list.load_balancer_pool
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)
        pod_network_cidr = get_k8s_cidr_info(k8s_config)

        # Create additional data for plugins (lbpool and cidr)
        template_fill_data = K8sPluginAdditionalData(areas=[lb_pool], pod_network_cidr=pod_network_cidr)

        helm_plugin_manager = HelmPluginManager(cluster.credentials, cluster_id)
        helm_plugin_manager.install_plugins(plug_to_install_list.plugin_list, template_fill_data)

        self.logger.success(f"Plugins {plug_to_install_list.plugin_list} have been installed")

    def apply_to_k8s(self, cluster_id: str, body):
        """
        Apply a yaml to a k8s cluster. It is like 'kubectl apply -f file.yaml'

        Args:
            cluster_id: The target cluster
            body: The yaml content to be applied at the cluster.
        """
        cluster: TopologyK8sModel = self.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        # Loading a yaml in this way result in a dictionary
        dict_request = yaml.safe_load_all(body)

        try:
            # The dictionary can be composed of multiple documents (divided by --- in the yaml)
            for document in dict_request:
                result = apply_def_to_cluster(kube_client_config=k8s_config, dict_to_be_applied=document)
        except FailToCreateError as err:
            self.logger.error(err)
            if err.args[0][0].status == 409:
                msg_err = "At least one of the yaml resources already exist"
            else:
                msg_err = err
            raise ValueError(msg_err)
        # Element in position zero because apply_def_to_cluster is working on dictionary, please look at the source
        # code of apply_def_to_cluster
        list_to_ret: List[dict] = []
        for element in result[0]:
            list_to_ret.append(element.to_dict())

        self.logger.success("Successfully applied to cluster. Created resources are: \n {}".format(list_to_ret))


# ----- Global functions for multiprocessing compatibility -----
# It requires functions in the namespace of the file (not in classes)

def initialize_k8s_man_subscriber(lock: RLock):
    """
    Start new K8S manager.

    Args:
        lock: The topology lock
    """

    # Start a subprocess that will listen to a redis topic
    Process(target=__start, args=(lock,)).start()


def __start(lock: RLock):
    """
    Generate a new manager in order to listen at the k8s management topic.
    Setup signals handler for closing K8S manager.
    Start listening at the incoming messages from redis.
    """
    k8s_instance = K8sManager(lock)

    atexit.register(k8s_instance.close)
    signal.signal(signal.SIGTERM, k8s_instance.close)
    signal.signal(signal.SIGINT, k8s_instance.close)

    k8s_instance.listen_to_k8s_management()
