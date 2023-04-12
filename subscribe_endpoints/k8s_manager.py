import json
import threading
from logging import Logger
from multiprocessing import Process, RLock
from typing import List
import redis
import yaml
from kubernetes.utils import FailToCreateError
from pydantic import ValidationError
from redis.client import PubSub
from models.k8s.k8s_models import K8sModelManagement, K8sOperationType, K8sModel, K8sPluginName
from nfvo import NbiUtil
from topology import Topology
from utils.k8s import install_plugins_to_cluster, get_k8s_config_from_file_content, \
    convert_str_list_2_plug_name, apply_def_to_cluster
from utils.log import create_logger
from utils.persistency import OSSdb
from utils.redis.redis_manager import get_redis_instance
from utils.redis.topic_list import K8S_MANAGEMENT_TOPIC

# ------ Utils
redis_cli: redis.Redis = get_redis_instance()
subscriber: PubSub = redis_cli.pubsub()
logger: Logger = create_logger("K8S MAN")


#
# Look at the bottom for singleton pattern implementation!
#

class K8sManager:
    def __init__(self, db: OSSdb, nbiutil: NbiUtil, lock: RLock):
        self.db: OSSdb = db
        self.nbiutil: NbiUtil = nbiutil
        self.lock: RLock = lock
        self.stop: bool = False
        self.locker = threading.RLock()

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

    def close(self):
        """
        Close this manager. THREAD SAFE
        """
        logger.debug("Closing process...")
        self.locker.acquire()
        self.stop = True
        self.locker.release()
        logger.debug("Process closed.")

    def get_k8s_cluster_by_id(self, cluster_id: str) -> K8sModel:
        """
        Get the k8s cluster from the topology. This method could be duplicated but in this case handle HTTP exceptions
        that give API user an idea of what is going wrong.

        Args:

            cluster_id: the cluster ID that identify a k8s cluster in the topology.

        Returns:

            The matching k8s cluster or Throw HTTPException if NOT found.
        """
        try:
            topology = Topology.from_db(self.db, self.nbiutil, self.lock)
            k8s_clusters: List[K8sModel] = topology.get_k8scluster_model()
            match = next((x for x in k8s_clusters if x.name == cluster_id), None)

            if match:
                return match
            else:
                msg_err = "K8s cluster {} not found".format(cluster_id)
                logger.error(msg_err)
                raise ValueError(msg_err)
        except Exception as err:
            logger.error(err)

    def listen_to_k8s_management(self):
        """
        This function is continuously listening for new message on the K8S_MANAGEMENT_TOPIC.

        When a new message comes from the redis subscription
        """
        for message in subscriber.listen():
            # If stop the for loop is exited and the process die
            if self.is_closed():
                break
            try:
                self._delegate_operation(message)
            except Exception as e:
                logger.error("Error while executing required operation: {}".format(message))
                logger.error(e)

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
            logger.info("Successfully subscribed to topic: {}".format(K8S_MANAGEMENT_TOPIC))
        elif message['type'] == 'unsubscribe':
            # Unsubscription confirmation
            logger.info("Successfully unsubscribed from topic: {}".format(K8S_MANAGEMENT_TOPIC))
        elif message['type'] == 'message':
            try:
                management_model: K8sModelManagement = K8sModelManagement.parse_obj(json.loads(data))
            except ValidationError:
                msg_err = "Received model, from subscription, is impossible to validate"
                logger.error(msg_err)
                raise ValidationError
            logger.info("Received operation {}. Starting processing the request...".format(management_model.k8s_ops))
            if management_model.k8s_ops == K8sOperationType.INSTALL_PLUGIN:
                self.install_plugins(management_model.cluster_id, json.loads(management_model.data))
            elif management_model.k8s_ops == K8sOperationType.APPLY_YAML:
                self.apply_to_k8s(management_model.cluster_id, management_model.data)
            else:
                logger.warning("Operation {} not supported".format(management_model.k8s_ops))
        else:
            msg_err = "Redis message type not recognized."
            logger.error(msg_err)
            raise ValidationError(msg_err)

    def install_plugins(self, cluster_id: str, plug_to_install: List[str]):
        """
        Install a plugin to a target k8s cluster

        Args:
            cluster_id: The target k8s cluster

            plug_to_install: The list, of enabled plugins, to be installed
        """
        # Getting k8s cluster from topology
        cluster = self.get_k8s_cluster_by_id(cluster_id)

        # Converting List[str] to List[K8sPluginNames]
        plugin_list: List[K8sPluginName] = convert_str_list_2_plug_name(plug_to_install)

        # Get k8s cluster and k8s config for client
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        try:
            # Try to install plugins to cluster
            installation_result: dict = install_plugins_to_cluster(kube_client_config=k8s_config,
                                                                   plugins_to_install=plugin_list)
            # Inspect installation_result for detailed info on the installation
        except ValueError as val_err:
            raise val_err

        # Return only the name of installed plugins
        to_print = []
        for plugin_result in installation_result:
            to_print.append(plugin_result)

        logger.info("Plugins {} have been installed".format(to_print))

    def apply_to_k8s(self, cluster_id: str, body):
        """
        Apply a yaml to a k8s cluster. It is like 'kubectl apply -f file.yaml'

        Args:
            cluster_id: The target cluster
            body: The yaml content to be applied at the cluster.
        """
        cluster: K8sModel = self.get_k8s_cluster_by_id(cluster_id)
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        yaml_request = yaml.safe_load(body)

        try:
            result = apply_def_to_cluster(kube_client_config=k8s_config, dict_to_be_applied=yaml_request)
        except FailToCreateError as err:
            logger.error(err)
            if err.args[0][0].status == 409:
                msg_err = "At least one of the yaml resources already exist"
            else:
                msg_err = "Error while creating resources"
            raise ValueError(msg_err)
        # Element in position zero because apply_def_to_cluster is working on dictionary, please look at the source
        # code of apply_def_to_cluster
        list_to_ret: List[dict] = []
        for element in result[0]:
            list_to_ret.append(element.to_dict())

        logger.info("Successfully applied to cluster. Created resources are: \n {}".format(list_to_ret))


#
k8s_instance: K8sManager = None


def initialize_k8s_man_subscriber_test(db: OSSdb, nbiutil: NbiUtil, lock: RLock) -> K8sManager:
    """
    Instantiate a k8s manager if it is not already present. Then it start the manager that will listen on his redis topic.

    Args:
        db: The database
        nbiutil: The nbiUtil from main
        lock: The topology lock

    Returns:
        The instantiated K8s manager
    """
    global k8s_instance
    if k8s_instance is None:
        k8s_instance = K8sManager(db, nbiutil, lock)
    # Start a sub process that will listen on redis topic
    Process(target=__start).start()
    return k8s_instance


def __start():
    """
    This method is necessary because Process start require that the method is in the file namespace, not inside a class.
    """
    global k8s_instance
    k8s_instance.listen_to_k8s_management()
