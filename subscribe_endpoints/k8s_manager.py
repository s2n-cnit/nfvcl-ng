import atexit
import json
import os
import signal
import threading
from logging import Logger
from multiprocessing import Process, RLock
from typing import List
import kubernetes
import redis
import traceback
import yaml
from kubernetes.utils import FailToCreateError
from pydantic import ValidationError
from redis.client import PubSub
from models.k8s.blueprint_k8s_model import LBPool
from models.k8s.plugin_k8s_model import K8sPluginsToInstall, K8sTemplateFillData, K8sOperationType, K8sPluginName
from models.k8s.topology_k8s_model import K8sModelManagement, K8sModel
from nfvo import NbiUtil
from topology.topology import Topology
from utils.k8s import install_plugins_to_cluster, get_k8s_config_from_file_content, \
    convert_str_list_2_plug_name, apply_def_to_cluster, get_k8s_cidr_info
from utils.log import create_logger
from utils.persistency import OSSdb
from utils.redis_utils.redis_manager import get_redis_instance
from utils.redis_utils.topic_list import K8S_MANAGEMENT_TOPIC


class K8sManager:
    redis_cli: redis.Redis = get_redis_instance()
    subscriber: PubSub = redis_cli.pubsub()
    logger: Logger
    db: OSSdb
    nbiutil: NbiUtil
    lock: RLock
    stop: bool

    def __init__(self, db: OSSdb, nbiutil: NbiUtil, lock: RLock):
        """
        Initialize the object and start logger + redis client.
        """
        self.db = db
        self.nbiutil = nbiutil
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

    def get_k8s_cluster_by_id(self, cluster_id: str) -> K8sModel:
        """
        Get the k8s cluster from the topology. This method could be duplicated but in this case handle HTTP exceptions
        that give API user an idea of what is going wrong.

        Args:

            cluster_id: the cluster ID that identify a k8s cluster in the topology.

        Returns:

            The matching k8s cluster or Throw ValueError if NOT found.
        """
        topology = Topology.from_db(self.db, self.nbiutil, self.lock)
        k8s_clusters: List[K8sModel] = topology.get_k8s_clusters()
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

        # Extracting names from K8sPluginToInstall list
        plugin_names_raw_list: List[K8sPluginName] = plug_to_install_list.plugin_list
        # Extracting additional data from K8sPluginToInstall list
        template_fill_data: K8sTemplateFillData = plug_to_install_list.template_fill_data

        # Converting List[str] to List[K8sPluginNames]
        plugin_name_list: List[K8sPluginName] = convert_str_list_2_plug_name(plugin_names_raw_list)

        # Get k8s cluster and k8s config for client
        k8s_config = get_k8s_config_from_file_content(cluster.credentials)

        # Checking data that will be used to fill file templates. Setting default values if empty.
        template_fill_data = self.check_and_reserve_template_data(template_fill_data, plugin_name_list, k8s_config,
                                                                  cluster_id=cluster_id)

        # Try to install plugins to cluster
        installation_result: dict = install_plugins_to_cluster(kube_client_config=k8s_config,
                                                               plugins_to_install=plugin_name_list,
                                                               template_fill_data=template_fill_data,
                                                               cluster_id=cluster_id,
                                                               skip_plug_checks=plug_to_install_list.skip_plug_checks)

        # Return only the name of installed plugins
        to_print = []
        for plugin_result in installation_result:
            to_print.append(plugin_result)

        self.logger.info("Plugins {} have been installed".format(to_print))

    def apply_to_k8s(self, cluster_id: str, body):
        """
        Apply a yaml to a k8s cluster. It is like 'kubectl apply -f file.yaml'

        Args:
            cluster_id: The target cluster
            body: The yaml content to be applied at the cluster.
        """
        cluster: K8sModel = self.get_k8s_cluster_by_id(cluster_id)
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

        self.logger.info("Successfully applied to cluster. Created resources are: \n {}".format(list_to_ret))

    def check_and_reserve_template_data(self, template_data: K8sTemplateFillData, plugin_to_install: List[K8sPluginName],
                                        kube_client_config: kubernetes.client.Configuration,
                                        cluster_id: str) -> K8sTemplateFillData:
        """
        Check the data to fill the template with.
        It is not possible to reserve the desire range of LBpool but only the range e the net name should be present.

        Args:
            template_data: The data that will be checked
            plugin_to_install: The list of plugins that will be installed (plugins templates require different data)
            kube_client_config: The config of cluster on witch we are working. (Used to retrieve pod cidr if not specified in the
            template data).
            cluster_id: The ID of cluster on witch we are working

        Returns:
            The checked template data, filled with missing information.
        """

        # Flannel and calico require pod_network_cidr to be configured
        if K8sPluginName.FLANNEL in plugin_to_install or K8sPluginName.CALICO in plugin_to_install:
            if not template_data.pod_network_cidr:
                template_data.pod_network_cidr = get_k8s_cidr_info(kube_client_config)

        # Metallb require an IP pool to be assigned at the load balancers
        if K8sPluginName.METALLB in plugin_to_install:
            cluster: K8sModel = self.get_k8s_cluster_by_id(cluster_id)

            topology: Topology = Topology.from_db(db=self.db, nbiutil=self.nbiutil, lock=self.lock)

            if not template_data.lb_pools:
                # If no load balancer pool is given
                # Taking the FIRST network of the k8s cluster and reserving 20 addresses. THERE SHOULD BE AT LEAST 1.
                network_name = cluster.networks[0]
                reserved_range = topology.reserve_range(net_name=network_name, range_length=20,
                                                        owner=cluster_id)
                lb_pool = LBPool(mode='layer2', net_name=network_name, ip_start=reserved_range.start,
                                 ip_end=reserved_range.end, range_length=20)
                template_data.lb_pools = [lb_pool]
            else:
                # Checking that every single network is in k8s cluster and reserving the desired range length.
                # Ignoring ip_start and ip_end if present. If no range length, 20 is assumed.
                for pool in template_data.lb_pools:
                    network_name = pool.net_name
                    if network_name in cluster.networks:
                        if not pool.range_length:
                            pool.range_length = 20
                        reserved_range = topology.reserve_range(net_name=network_name, range_length=pool.range_length,
                                                                owner=cluster_id)
                        pool.ip_start = reserved_range.start
                        pool.ip_end = reserved_range.end
                    else:
                        raise ValueError("The network {} is not present inside k8s {} cluster.".format(network_name,
                                                                                                       cluster.name))
        # Returning checked template data
        return template_data


# ----- Global functions for multiprocessing compatibility -----
# It requires functions in the namespace of the file (not in classes)

def initialize_k8s_man_subscriber(db: OSSdb, nbiutil: NbiUtil, lock: RLock):
    """
    Start new K8S manager.

    Args:
        db: The database
        nbiutil: The nbiUtil from main
        lock: The topology lock
    """

    # Start a sub process that will listen on redis topic
    Process(target=__start, args=(db, nbiutil, lock)).start()


def __start(db: OSSdb, nbiutil: NbiUtil, lock: RLock):
    """
    Generate a new manager in order to listen at the k8s management topic.
    Setup signals handler for closing K8S manager.
    Start listening at the incoming messages from redis.
    """
    k8s_instance = K8sManager(db, nbiutil, lock)

    atexit.register(k8s_instance.close)
    signal.signal(signal.SIGTERM, k8s_instance.close)
    signal.signal(signal.SIGINT, k8s_instance.close)

    k8s_instance.listen_to_k8s_management()
