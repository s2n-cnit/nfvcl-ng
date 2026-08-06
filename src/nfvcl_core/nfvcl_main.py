import threading
from functools import partial
from http import HTTPStatus
from typing import Callable, Dict, List, Any, Optional, Annotated

import urllib3
from dependency_injector.wiring import Provide
from pydantic import Field

from nfvcl.blueprints_ng.pdu_configurators.implementations import register_pdu_implementations
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_common.utils.file_utils import set_nfvcl_tmp_folder, set_nfvcl_mounted_folder
from nfvcl_common.utils.log import create_logger
from nfvcl_common.utils.nfvcl_public_utils import NFVCLPublicSectionModel, NFVCLPublic
from nfvcl_core import global_ref
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, BlueprintModule, BlueprintDay2Route
from nfvcl_core.containers.nfvcl_container import NFVCLContainer
from nfvcl_core.managers.blueprint_manager import BlueprintManager
from nfvcl_core.managers.event_manager import EventManager
from nfvcl_core.managers.kubernetes_manager import KubernetesManager
from nfvcl_core.managers.monitoring_manager import MonitoringManager
from nfvcl_core.managers.pdu_manager import PDUManager
from nfvcl_core.managers.performance_manager import PerformanceManager
from nfvcl_core.managers.provider_manager import ProviderManager
from nfvcl_core.managers.task_manager import TaskManager
from nfvcl_core.managers.topology_manager import TopologyManager
from nfvcl_core.managers.user_manager import UserManager
from nfvcl_core.public_methods_description import GET_PROM_SRV_SUMMARY, GET_PROM_SRV_DESCRIPTION, \
    GET_PROM_LIST_SRV_SUMMARY, GET_PROM_LIST_SRV_DESCRIPTION, DEL_PROM_SRV_SUMMARY, DEL_PROM_SRV_DESCRIPTION, \
    UPD_PROM_SRV_SUMMARY, UPD_PROM_SRV_DESCRIPTION, ADD_PROM_SRV_DESCRIPTION, ADD_PROM_SRV_SUMMARY, \
    UPD_K8SCLUSTER_SUMMARY, UPD_K8SCLUSTER_DESCRIPTION, ADD_EXTERNAL_K8SCLUSTER_SUMMARY, ADD_EXTERNAL_K8SCLUSTER
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel, BlueprintNGBaseModel
from nfvcl_core_models.config import NFVCLConfigModel
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.k8s_management_models import Labels
from nfvcl_core_models.monitoring.prometheus_model import PrometheusServerModel
from nfvcl_core_models.network.network_models import PduModel, NetworkModel, RouterModel, IPv4Pool, IPv4ReservedRange, IPv4ReservedRangeRequest
from nfvcl_core_models.performance import BlueprintPerformance
from nfvcl_core_models.plugin_k8s_model import K8sPluginsToInstall, K8sMonitoringConfig
from nfvcl_core_models.response_model import AsyncTaskResponse, AsyncTaskStatus
from nfvcl_core_models.task import NFVCLTaskResult, NFVCLTask, NFVCLTaskStatus, NFVCLTaskDeleteResult
from nfvcl_core_models.topology_k8s_model import TopologyK8sModel, K8sQuota, ProvidedBy
from nfvcl_core_models.topology_models import TopologyModel
from nfvcl_core_models.user import UserNoConfidence, UserCreateREST
from nfvcl_core_models.vim.vim_models import VimModel


def callback_function(event: threading.Event, namespace: Dict, msg: NFVCLTaskResult):
    namespace["msg"] = msg
    event.set()


class NFVCL:
    TOPOLOGY_SECTION = NFVCLPublicSectionModel(name="Topology", description="Operations related to the topology", path="/v1/topology")
    BLUEPRINTS_SECTION = NFVCLPublicSectionModel(name="Blueprints", description="Operations related to the blueprints", path="/nfvcl/v2/api/blue")
    SNAPSHOT_SECTION = NFVCLPublicSectionModel(name="Snapshots", description="Operations related to the snapshot of blueprints", path="/nfvcl/v2/api/snapshot")
    PERFORMANCE_SECTION = NFVCLPublicSectionModel(name="Performances", description="Operations related to the performance metrics", path="/performance/blue")
    K8S_SECTION = NFVCLPublicSectionModel(name="Kubernetes cluster management", description="Operations related to kubernetes clusters", path="/k8s")
    UTILS_SECTION = NFVCLPublicSectionModel(name="Utils", description="Utils", path="/v2/utils")
    TASK_SECTION = NFVCLPublicSectionModel(name="Tasks", description="Operations related to tasks", path="/v1/tasks")
    USER_SECTION = NFVCLPublicSectionModel(name="Users", description="User management", path="/v2/users")
    def __init__(
        self,
        config: NFVCLConfigModel = Provide[NFVCLContainer.config],
        task_manager: TaskManager = Provide[NFVCLContainer.task_manager],
        event_manager: EventManager = Provide[NFVCLContainer.event_manager],
        topology_manager: TopologyManager = Provide[NFVCLContainer.topology_manager],
        provider_manager: ProviderManager = Provide[NFVCLContainer.provider_manager],
        blueprint_manager: BlueprintManager = Provide[NFVCLContainer.blueprint_manager],
        performance_manager: PerformanceManager = Provide[NFVCLContainer.performance_manager],
        pdu_manager: PDUManager = Provide[NFVCLContainer.pdu_manager],
        kubernetes_manager: KubernetesManager = Provide[NFVCLContainer.kubernetes_manager],
        user_manager: UserManager = Provide[NFVCLContainer.user_manager],
        monitoring_manager: Optional[MonitoringManager] = Provide[NFVCLContainer.monitoring_manager],
    ):
        self.logger = create_logger(self.__class__.__name__)

        global_ref.nfvcl_config = NFVCLConfigModel.model_validate(config)
        set_nfvcl_tmp_folder(global_ref.nfvcl_config.nfvcl.tmp_folder)
        set_nfvcl_mounted_folder(global_ref.nfvcl_config.nfvcl.mounted_folder)

        self.topology_manager = topology_manager
        self.provider_manager = provider_manager
        self.blueprint_manager = blueprint_manager
        self.performance_manager = performance_manager
        self.kubernetes_manager = kubernetes_manager
        self.task_manager = task_manager
        self.event_manager = event_manager
        self.user_manager = user_manager
        self.monitoring_manager = monitoring_manager

        urllib3.disable_warnings()

        register_pdu_implementations(pdu_manager)

        if not global_ref.nfvcl_config.nfvcl.rescue_mode:
            self.blueprint_manager.load()
            self.performance_manager.load()
        self.user_manager.load()

        # TODO rework plugin loading
        from nfvcl_core.plugins.plugin import NFVCLPlugin

        self.plugins: List[NFVCLPlugin] = []

        for plugin in self.plugins:
            plugin.load()

    VIM_SECTION = NFVCLPublicSectionModel(name="Virtualization provider", description="User management", path="/v2/vim")

    def get_ordered_public_methods(self) -> List[Callable]:
        """
        Get the list of all public methods that should be exposed by the NFVCL
        Returns: List of public methods callable
        """
        public_methods = []
        for attr in dir(self):
            if callable(getattr(self, attr)) and hasattr(getattr(self, attr), "nfvcl_public"):
                public_methods.append(getattr(self, attr))

        # add Plugins public methods
        for plugin in self.plugins:
            for attr in dir(plugin):
                if callable(getattr(plugin, attr)) and hasattr(getattr(plugin, attr), "nfvcl_public"):
                    public_methods.append(getattr(plugin, attr))

        return sorted(public_methods, key=lambda x: x.order)

    def _add_task_sync(self, function: Callable, *args, **kwargs):
        event = threading.Event()
        # used to receive the return data from the function
        namespace = {}
        self.task_manager.add_task(NFVCLTask(function, partial(callback_function, event, namespace), *args, **kwargs))
        event.wait()
        task_result: NFVCLTaskResult = namespace["msg"]
        if task_result.error:
            raise task_result.exception
        return namespace["msg"]

    def _add_task_async(self, function: Callable, *args, **kwargs) -> AsyncTaskResponse:
        callback: Optional[Callable] = kwargs.pop("callback", None)
        async_response: AsyncTaskResponse = kwargs.pop("async_response", AsyncTaskResponse(status=AsyncTaskStatus.processing, detail="Operation queued"))
        task = NFVCLTask(function, callback, *args, **kwargs)
        try:
            task_id = self.task_manager.add_task(task)
        except Exception:
            if task.on_cancel:
                task.on_cancel()
            raise
        async_response.task_id = task_id
        return async_response

    def add_task(self, function, *args, **kwargs):
        callback: Optional[Callable] = kwargs.pop("callback", None)

        # TODO check if the function is sync or async
        if callback is None:
            return self._add_task_sync(function, *args, **kwargs).result
        else:
            return self._add_task_async(function, *args, **kwargs, callback=callback)

    def get_loaded_blueprints(self) -> List[BlueprintModule]:
        return list(blueprint_type.get_registered_modules().values())

    def get_module_routes(self, prefix) -> List[BlueprintDay2Route]:
        return blueprint_type.get_module_routes(prefix)

    ##################################################################
    ######################## REST API ################################
    ##################################################################

    ##################################################################
    ##################      TASK SECTION      ########################
    ##################################################################

    @NFVCLPublic(path="", section=TASK_SECTION, method=HttpRequestType.GET, sync=True)
    def get_queued_running_tasks(self) -> List[NFVCLTaskStatus]:
        """
        Get the list of queued and running tasks.

        Returns: List of NFVCLTaskStatus with "queued" or "running" status.
        """
        return self.task_manager.list_queued_running_tasks()

    @NFVCLPublic(path="/{task_id}", section=TASK_SECTION, method=HttpRequestType.GET, sync=True)
    def get_task_status(self, task_id: str) -> NFVCLTaskStatus:
        """
        Get the status of a task given its task_id

        Warnings:
            If NFVCL is restarted the task_id will be lost and the task will not be found
        Args:
            task_id: ID of the task to get the status of

        Returns: NFVCLTaskStatus, the "status" field can be "queued", "running" or "done"
        """
        task_status = self.task_manager.get_task_status(task_id)
        if task_status is None:
            raise NFVCLCoreException(message="Task not found", http_equivalent_code=404)
        return task_status

    @NFVCLPublic(path="/{task_id}", section=TASK_SECTION, method=HttpRequestType.DELETE, sync=True)
    def delete_queued_task(self, task_id: str) -> NFVCLTaskDeleteResult:
        """
        Delete a task that has been queued but not started yet.

        Args:
            task_id: ID of the task to delete

        Returns: NFVCLTaskDeleteResult for the deleted task
        """
        delete_result = self.task_manager.delete_queued_task(task_id)
        if delete_result is None:
            raise NFVCLCoreException(message="Task not found", http_equivalent_code=404)
        if not delete_result:
            raise NFVCLCoreException(message="Task already started and cannot be deleted", http_equivalent_code=409)
        return NFVCLTaskDeleteResult(task_id=task_id)

    ##################################################################
    ##################      TOPOLOGY SECTION      ####################
    ##################################################################

    @NFVCLPublic(path="", section=TOPOLOGY_SECTION, method=HttpRequestType.GET, sync=True)
    def get_topology(self) -> TopologyModel:
        """
        Get information regarding the managed topology
        """
        return self.topology_manager.get_topology()

    @NFVCLPublic(path="", section=TOPOLOGY_SECTION, method=HttpRequestType.POST, sync=True)
    def create_topology(self, topology: TopologyModel):
        """
        Create the topology
        """
        return self.topology_manager.create_topology(topology)

    @NFVCLPublic(path="", section=TOPOLOGY_SECTION, method=HttpRequestType.DELETE, sync=True)
    def delete_topology(self):
        return self.topology_manager.delete_topology()

    @NFVCLPublic(path="/vim/{vim_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.GET, sync=True)
    def get_vim(self, vim_id: str) -> VimModel:
        return self.topology_manager.get_vim(vim_id)

    @NFVCLPublic(path="/vim", section=TOPOLOGY_SECTION, method=HttpRequestType.POST, sync=True)
    def create_vim(self, vim: VimModel):
        return self.topology_manager.create_vim(vim)

    @NFVCLPublic(path="/vim/update", section=TOPOLOGY_SECTION, method=HttpRequestType.PUT, sync=True)
    def update_vim(self, vim: VimModel):
        return self.topology_manager.update_vim(vim)

    @NFVCLPublic(path="/vim/{vim_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.DELETE, sync=True)
    def delete_vim(self, vim_id: str):
        self.topology_manager.delete_vim(vim_id)

    @NFVCLPublic(path="/network", section=TOPOLOGY_SECTION, method=HttpRequestType.GET, sync=True)
    def get_networks(self) -> List[NetworkModel]:
        return self.topology_manager.get_networks()

    @NFVCLPublic(path="/network/{network_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.GET, sync=True)
    def get_network(self, network_id: str) -> NetworkModel:
        return self.topology_manager.get_network(network_id)

    @NFVCLPublic(path="/network", section=TOPOLOGY_SECTION, method=HttpRequestType.POST, sync=True)
    def create_network(self, network: NetworkModel):
        return self.topology_manager.create_network(network)

    @NFVCLPublic(path="/network", section=TOPOLOGY_SECTION, method=HttpRequestType.PUT, sync=True)
    def update_network(self, network: NetworkModel):
        return self.topology_manager.create_network(network)

    @NFVCLPublic(path="/network/{network}/pool", section=TOPOLOGY_SECTION, method=HttpRequestType.POST, sync=True)
    def add_pool_network(self, network: str, pool: IPv4Pool) -> IPv4Pool:
        return self.topology_manager.add_allocation_pool_to_network(network, pool)

    @NFVCLPublic(path="/network/{network}/pool/{pool_name}", section=TOPOLOGY_SECTION, method=HttpRequestType.DELETE, sync=True)
    def del_pool_network(self, network: str, pool_name: str) -> IPv4Pool:
        return self.topology_manager.remove_allocation_pool_from_network(network, pool_name)

    @NFVCLPublic(path="/network/{network}/reserved_range_k8s", section=TOPOLOGY_SECTION, method=HttpRequestType.POST, sync=True, doc_by=TopologyManager.reserve_range_to_k8s_cluster)
    def reserve_range_to_k8s_cluster(self, network: str, reserved_range_k8s: IPv4ReservedRangeRequest) -> List[IPv4ReservedRange]:
        return self.topology_manager.reserve_range_to_k8s_cluster(network, reserved_range_k8s)

    @NFVCLPublic(path="/network/{network}/reserved_range_k8s/{reserved_range_name}/{k8s_cluster_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.DELETE, sync=True, doc_by=TopologyManager.release_range_from_k8s_cluster)
    def release_range_to_k8s_cluster(self, network: str, reserved_range_name: str, k8s_cluster_id: str) -> IPv4ReservedRange:
        return self.topology_manager.release_range_from_k8s_cluster(network, reserved_range_name, k8s_cluster_id)

    @NFVCLPublic(path="/network/{network_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.DELETE, sync=True)
    def delete_network(self, network_id: str):
        self.topology_manager.delete_network(network_id)

    @NFVCLPublic(path="/router/{router_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.GET, sync=True)
    def get_router(self, router_id: str) -> RouterModel:
        return self.topology_manager.get_router(router_id)

    @NFVCLPublic(path="/router", section=TOPOLOGY_SECTION, method=HttpRequestType.POST, sync=True)
    def create_router(self, router: RouterModel) -> RouterModel:
        return self.topology_manager.create_router(router)

    @NFVCLPublic(path="/router/{router_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.DELETE, sync=True)
    def delete_router(self, router_id: str):
        self.topology_manager.delete_router(router_id)

    @NFVCLPublic(path="/pdus", section=TOPOLOGY_SECTION, method=HttpRequestType.GET, sync=True)
    def get_pdus(self) -> List[PduModel]:
        return self.topology_manager.get_pdus()

    @NFVCLPublic(path="/pdu/{pdu_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.GET, sync=True)
    def get_pdu(self, pdu_id: str) -> PduModel:
        return self.topology_manager.get_pdu(pdu_id)

    @NFVCLPublic(path="/pdu", section=TOPOLOGY_SECTION, method=HttpRequestType.POST, sync=True)
    def create_pdu(self, pdu: PduModel):
        return self.topology_manager.create_pdu(pdu)

    @NFVCLPublic(path="/pdu/{pdu_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.DELETE, sync=True)
    def delete_pdu(self, pdu_id: str):
        self.topology_manager.delete_pdu(pdu_id)

    # @NFVCLPublic(path="/pdu/{pdu_id}/force_unlock", section=TOPOLOGY_SECTION, method=HttpRequestType.POST)
    # def force_unlock_pdu(self, pdu_id: str, callback=None):
    #     return self.topology_manager.force_unlock_pdu(pdu_id)

    @NFVCLPublic(path="/kubernetes", section=TOPOLOGY_SECTION, method=HttpRequestType.GET, sync=True)
    def get_kubernetes_list(self) -> List[TopologyK8sModel]:
        return self.topology_manager.get_kubernetes_list()

    @NFVCLPublic(path="/kubernetes/{cluster_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.GET, sync=True)
    def get_kubernetes(self, cluster_id: str) -> TopologyK8sModel:
        return self.topology_manager.get_k8s_cluster_by_id(cluster_id)

    @NFVCLPublic(
        path="/kubernetes_external",
        section=TOPOLOGY_SECTION,
        method=HttpRequestType.POST,
        summary=ADD_EXTERNAL_K8SCLUSTER_SUMMARY,
        description=ADD_EXTERNAL_K8SCLUSTER, sync=True
    )
    def create_kubernetes_external(self, kubernetes_model: TopologyK8sModel):
        kubernetes_model.provided_by = ProvidedBy.EXTERNAL
        return self.topology_manager.add_kubernetes(kubernetes_model)

    @NFVCLPublic(path="/kubernetes/update", section=TOPOLOGY_SECTION, method=HttpRequestType.PUT, summary=UPD_K8SCLUSTER_SUMMARY, description=UPD_K8SCLUSTER_DESCRIPTION, sync=True)
    def update_kubernetes(self, cluster: TopologyK8sModel) -> TopologyK8sModel:
        return self.topology_manager.update_kubernetes(cluster)

    @NFVCLPublic(path="/kubernetes/{cluster_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.DELETE, sync=True)
    def delete_kubernetes(self, cluster_id: str, force_deletion: bool = False) -> TopologyK8sModel:
        return self.topology_manager.delete_kubernetes(cluster_id, force_deletion=force_deletion)

    ##################################################################
    ##################      VIM   SECTION    #########################
    ##################################################################

    @NFVCLPublic(path="/networks/{area}", section=VIM_SECTION, method=HttpRequestType.GET, sync=True)
    def get_vim_networks(self, area: Annotated[int,Field(gt=0)]) -> List[NetworkModel]:
        """
        Returns a list of networks for the given area, retrieved directly from the Hypervisor.
        Args:
            area: The area identifier for which to retrieve the networks.

        Returns:
            A list of NetworkModel objects representing the networks in the specified area.
        """
        provider = self.provider_manager.get_virtualization_provider_for_area(area)
        return provider.get_networks()

    @NFVCLPublic(path="/networks/{area}/{network_name}", section=VIM_SECTION, method=HttpRequestType.GET, sync=True)
    def get_vim_network(self, area: Annotated[int,Field(gt=0)], network_name: str) -> NetworkModel:
        """
        Fetches the network information for a given network name and area from the hypervisor.

        This method interacts with the virtualization provider associated with the
        specified area to retrieve details about the requested network. It allows the
        caller to retrieve network metadata and properties.

        Args:
            network_name (str): The unique identifier of the network to fetch.
            area (int): The area identifier, constrained to positive integers.

        Returns:
            NetworkModel: An object representing the network's details and properties.
        """
        provider = self.provider_manager.get_virtualization_provider_for_area(area)
        network = provider.get_net(network_name, area)
        if network is None:
            raise NFVCLCoreException(f"Network '{network_name}' not found in area {area}", http_equivalent_code=HTTPStatus.NOT_FOUND)
        return network

    ##################################################################
    ##################      PROMETHEUS SECTION    ####################
    ##################################################################

    @NFVCLPublic(path="/prometheus",section=TOPOLOGY_SECTION,method=HttpRequestType.GET,sync=True,summary=GET_PROM_LIST_SRV_SUMMARY,description=GET_PROM_LIST_SRV_DESCRIPTION)
    def get_prometheus_list(self) -> List[PrometheusServerModel]:
        return self.topology_manager.get_prometheus_list()

    @NFVCLPublic(path="/prometheus/{prometheus_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.GET, sync=True, summary=GET_PROM_SRV_SUMMARY, description=GET_PROM_SRV_DESCRIPTION)
    def get_prometheus(self, prometheus_id: str) -> PrometheusServerModel:
        return self.topology_manager.get_prometheus(prometheus_id)

    @NFVCLPublic(path="/prometheus", section=TOPOLOGY_SECTION, method=HttpRequestType.POST, summary=ADD_PROM_SRV_SUMMARY, description=ADD_PROM_SRV_DESCRIPTION, sync=True)
    def create_prometheus(self, prometheus_model: PrometheusServerModel) -> PrometheusServerModel:
        return self.topology_manager.add_prometheus(prometheus_model)

    @NFVCLPublic(path="/prometheus", section=TOPOLOGY_SECTION, method=HttpRequestType.PUT, summary=UPD_PROM_SRV_SUMMARY, description=UPD_PROM_SRV_DESCRIPTION, sync=True)
    def update_prometheus(self, prometheus_model: PrometheusServerModel) -> PrometheusServerModel:
        return self.topology_manager.update_prometheus(prometheus_model)

    @NFVCLPublic( path="/prometheus/{prometheus_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.DELETE, summary=DEL_PROM_SRV_SUMMARY, description=DEL_PROM_SRV_DESCRIPTION, sync=True)
    def delete_prometheus(self, prometheus_id: str):
        return self.topology_manager.delete_prometheus(prometheus_id)

    @NFVCLPublic( path="/prometheus/{prometheus_id}", section=TOPOLOGY_SECTION, method=HttpRequestType.PATCH, summary="Refresh file on remote Prometheus", sync=True)
    def trigger_file_upload(self, prometheus_id: str) -> PrometheusServerModel:
        return self.monitoring_manager.sync_prometheus_targets_to_server(prometheus_id)

    #####################
    # Blueprint Section #
    #####################

    @NFVCLPublic(path="", section=BLUEPRINTS_SECTION, method=HttpRequestType.GET, sync=True)
    def get_blueprints(self, blue_type: str | None = None, detailed: bool = False, tree: bool = False) -> List[dict]:
        return self.blueprint_manager.get_blueprint_summary_list(blue_type, detailed, tree)

    @NFVCLPublic(path="/{blueprint_id}", section=BLUEPRINTS_SECTION, method=HttpRequestType.GET, sync=True)
    def get_blueprint(self, blueprint_id: str, detailed: bool = False) -> dict:
        return self.blueprint_manager.get_blueprint_summary_by_id(blueprint_id, detailed)

    # @NFVCLPublic(path="", section=BLUEPRINTS_SECTION, method=HttpRequestType.POST)
    def create_blueprint(self, blue_type: str, msg: BlueprintNGCreateModel, callback=None):
        if callback is None:
            return self.add_task(self.blueprint_manager.create_blueprint, blue_type, msg, callback=callback)
        # Here we get the response that will be sent to the user, we need to do this mainly to have the blueprint ID in there
        async_response = self.blueprint_manager.precheck_create_blueprint(blue_type, msg)
        if async_response.status == AsyncTaskStatus.failed:
            return async_response
        # We call the actual create_blueprint passing the pregenerated blueprint ID
        # The _on_cancel is used to release the allocated blueprint ID in case of task cancellation
        # The async_response, callback and _on_cancel are passed to _add_task_async and to the task object while blueprint_id to create_blueprint
        # TODO Find a way to not mix caller and called function parameters for better readability
        return self._add_task_async(
            self.blueprint_manager.create_blueprint,
            blue_type,
            msg,
            async_response=async_response,
            blueprint_id=async_response.blueprint_id,
            callback=callback,
            _on_cancel=partial(self.blueprint_manager.release_reserved_blueprint_id, async_response.blueprint_id),
        )

    # @NFVCLPublic(path="", section=BLUEPRINTS_SECTION, method=HttpRequestType.PUT)
    def update_blueprint(self, blue_id: str, day2_path: str, msg: Any = None, callback=None):
        if callback is None:
            return self.add_task(self.blueprint_manager.update_blueprint, blue_id, day2_path, msg, callback=callback)
        async_response = self.blueprint_manager.precheck_update_blueprint(blue_id, day2_path, msg)
        if async_response.status == AsyncTaskStatus.failed:
            return async_response
        return self._add_task_async(self.blueprint_manager.update_blueprint, blue_id, day2_path, msg, async_response=async_response, callback=callback)

    # @NFVCLPublic(path="/get_from_blueprint", section=BLUEPRINTS_SECTION, method=HttpRequestType.GET)
    def get_from_blueprint(self, blue_id: str, day2_path: str, callback=None) -> Any:
        return self.add_task(self.blueprint_manager.get_from_blueprint, blue_id, day2_path, callback=callback)

    @NFVCLPublic(path="/{blueprint_id}", section=BLUEPRINTS_SECTION, method=HttpRequestType.DELETE)
    def delete_blueprint(self, blueprint_id: str, force_deletion: bool = False, callback=None):
        if callback is None:
            return self.add_task(self.blueprint_manager.delete_blueprint, blueprint_id, force_deletion=force_deletion,callback=callback)
        async_response = self.blueprint_manager.precheck_delete_blueprint(blueprint_id, force_deletion=force_deletion)
        if async_response.status == AsyncTaskStatus.failed:
            return async_response
        return self._add_task_async(self.blueprint_manager.delete_blueprint, blueprint_id, force_deletion=force_deletion, async_response=async_response, callback=callback)

    @NFVCLPublic(path="/all/blue", section=BLUEPRINTS_SECTION, method=HttpRequestType.DELETE)
    def delete_all_blueprints(self, callback=None):
        if callback is None:
            return self.add_task(self.blueprint_manager.delete_all_blueprints, callback=callback)
        async_response = self.blueprint_manager.precheck_delete_all_blueprints()
        if async_response.status == AsyncTaskStatus.failed:
            return async_response
        return self._add_task_async(self.blueprint_manager.delete_all_blueprints, async_response=async_response, callback=callback)

    @NFVCLPublic(path="/protect/{blueprint_id}", section=BLUEPRINTS_SECTION, method=HttpRequestType.PATCH, sync=True)
    def protect_blueprint(self, blueprint_id: str, protect: bool) -> dict:
        return self.blueprint_manager.protect_blueprint(blueprint_id, protect)

    @NFVCLPublic(path="/{snapshot_name}", section=SNAPSHOT_SECTION, method=HttpRequestType.GET, sync=True)
    def get_snapshot(self, snapshot_name: str) -> BlueprintNGBaseModel:
        return self.blueprint_manager.get_snapshot(snapshot_name)

    @NFVCLPublic(path="/", section=SNAPSHOT_SECTION, method=HttpRequestType.GET, sync=True)
    def get_snapshot_list(self) -> List[BlueprintNGBaseModel]:
        return self.blueprint_manager.get_snapshot_list()

    @NFVCLPublic(path="/{blueprint_id}", section=SNAPSHOT_SECTION, method=HttpRequestType.POST, sync=True)
    def snapshot_blueprint(self, blueprint_id: str, snapshot_name: str) -> BlueprintNGBaseModel:
        return self.blueprint_manager.snapshot_blueprint(snapshot_name, blueprint_id)

    @NFVCLPublic(path="/restore/{snapshot_name}", section=SNAPSHOT_SECTION, method=HttpRequestType.POST)
    def snapshot_restore(self, snapshot_name: str, callback=None):
        if callback is None:
            return self.add_task(self.blueprint_manager.snapshot_restore, snapshot_name, callback=callback)
        async_response = self.blueprint_manager.precheck_snapshot_restore(snapshot_name)
        if async_response.status == AsyncTaskStatus.failed:
            return async_response
        return self._add_task_async(self.blueprint_manager.snapshot_restore, snapshot_name, async_response=async_response, callback=callback)

    @NFVCLPublic(path="/snapshot_and_delete/{blueprint_id}", section=SNAPSHOT_SECTION, method=HttpRequestType.POST)
    def snapshot_and_delete_blueprint(self, blueprint_id: str, snapshot_name: str, callback=None):
        if callback is None:
            return self.add_task(self.blueprint_manager.snapshot_and_delete, snapshot_name, blueprint_id, callback=callback)
        async_response = self.blueprint_manager.precheck_snapshot_and_delete(snapshot_name, blueprint_id)
        if async_response.status == AsyncTaskStatus.failed:
            return async_response
        return self._add_task_async(self.blueprint_manager.snapshot_and_delete, snapshot_name, blueprint_id, async_response=async_response, callback=callback)

    @NFVCLPublic(path="/{snapshot_name}", section=SNAPSHOT_SECTION, method=HttpRequestType.DELETE, sync=True)
    def delete_snapshot(self, snapshot_name: str) -> BlueprintNGBaseModel:
        return self.blueprint_manager.snapshot_delete(snapshot_name)

    ############# Performance #############

    @NFVCLPublic(path="/", section=PERFORMANCE_SECTION, method=HttpRequestType.GET, sync=True)
    def get_all_performances(self) -> List[BlueprintPerformance]:
        return self.performance_manager.get_all_performaces()

    @NFVCLPublic(path="/{blueprint_id}", section=PERFORMANCE_SECTION, method=HttpRequestType.GET, sync=True)
    def get_performance(self, blueprint_id: str) -> BlueprintPerformance:
        return self.performance_manager.get_blue_performance(blueprint_id)

    # @NFVCLPublic(path="/{blueprint_id}", section=PERFORMANCE_SECTION, method=HttpRequestType.DELETE)
    # def delete_performance(self, blueprint_id: str, callback=None):
    #     return self._add_task(self._performance_manager.delete_performance, blueprint_id, callback=callback)

    #################################
    # Kubernetes cluster management #
    #################################

    @NFVCLPublic(path="/{cluster_id}/plugins", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_k8s_installed_plugins)
    def k8s_get_installed_plugins(self, cluster_id: str) -> List[str]:
        return self.kubernetes_manager.get_k8s_installed_plugins(cluster_id)

    @NFVCLPublic(path="/{cluster_id}/plugins", section=K8S_SECTION, method=HttpRequestType.PUT, sync=False, doc_by=KubernetesManager.install_plugins)
    def k8s_install_plugin(self, cluster_id: str, plugin_name: K8sPluginsToInstall, callback=None) -> AsyncTaskResponse:
        return self.add_task(self.kubernetes_manager.install_plugins, cluster_id, plugin_name, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/k8s_monitoring", section=K8S_SECTION, method=HttpRequestType.PUT, sync=False, doc_by=KubernetesManager.install_k8s_monitoring)
    def k8s_install_monitoring(self, cluster_id: str, monitoring_config: K8sMonitoringConfig, callback=None) -> AsyncTaskResponse:
        return self.add_task(self.kubernetes_manager.install_k8s_monitoring, cluster_id, monitoring_config, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/add_monitoring_destination", section=K8S_SECTION, method=HttpRequestType.PUT, sync=False, doc_by=KubernetesManager.add_monitoring_destination)
    def k8s_add_monitoring_destination(self, cluster_id: str, loki_id: Optional[str], prometheus_id: Optional[str], callback=None) -> AsyncTaskResponse:
        return self.add_task(self.kubernetes_manager.add_monitoring_destination, cluster_id, loki_id, prometheus_id, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/uninstall_plugin", section=K8S_SECTION, method=HttpRequestType.PUT, sync=False, doc_by=KubernetesManager.uninstall_plugin)
    def k8s_uninstall_plugin(self, cluster_id: str, namespace: str, callback=None) -> AsyncTaskResponse:
        return self.add_task(self.kubernetes_manager.uninstall_plugin, cluster_id, namespace, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/uninstall_k8s_monitoring", section=K8S_SECTION, method=HttpRequestType.PUT, sync=False, doc_by=KubernetesManager.uninstall_k8s_monitoring)
    def k8s_uninstall_monitoring(self, cluster_id: str, callback=None) -> AsyncTaskResponse:
        return self.add_task(self.kubernetes_manager.uninstall_k8s_monitoring, cluster_id, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/del_monitoring_destination", section=K8S_SECTION, method=HttpRequestType.PUT, sync=False, doc_by=KubernetesManager.del_monitoring_destination)
    def k8s_del_monitoring_destination(self, cluster_id: str, loki_id: Optional[str], prometheus_id: Optional[str], callback=None) -> AsyncTaskResponse:
        return self.add_task(self.kubernetes_manager.del_monitoring_destination, cluster_id, loki_id, prometheus_id, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/yaml", section=K8S_SECTION, method=HttpRequestType.PUT, sync=False, doc_by=KubernetesManager.apply_to_k8s)
    def k8s_apply_yaml(self, cluster_id: str, yaml: Annotated[str, "application/yaml"], callback=None) -> AsyncTaskResponse:
        return self.add_task(self.kubernetes_manager.apply_to_k8s, cluster_id, yaml, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/cidr", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_k8s_cidr)
    def k8s_get_cluster_cidr(self, cluster_id: str) -> dict:
        return self.kubernetes_manager.get_k8s_cidr(cluster_id)

    @NFVCLPublic(path="/{cluster_id}/ipaddresspools", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_k8s_ipaddress_pools)
    def k8s_get_ipaddresspools(self, cluster_id: str) -> List[str]:
        return self.kubernetes_manager.get_k8s_ipaddress_pools(cluster_id)

    @NFVCLPublic(path="/{cluster_id}/storageclasses", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_k8s_storage_classes)
    def k8s_get_storage_classes(self, cluster_id: str) -> List[str]:
        return self.kubernetes_manager.get_k8s_storage_classes(cluster_id)

    @NFVCLPublic(path="/{cluster_id}/defaultstorageclasses", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_k8s_default_storage_class)
    def k8s_get_default_storage_classes(self, cluster_id: str) -> str | None:
        return self.kubernetes_manager.get_k8s_default_storage_class(cluster_id)

    @NFVCLPublic(path="/{cluster_id}/pods", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_k8s_pods)
    def k8s_get_pods(self, cluster_id: str) -> dict:
        return self.kubernetes_manager.get_k8s_pods(cluster_id)

    @NFVCLPublic(path="/{cluster_id}/namespaces", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_k8s_namespace_list)
    def k8s_get_namespace_list(self, cluster_id: str, namespace: Optional[str] = None) -> dict:
        return self.kubernetes_manager.get_k8s_namespace_list(cluster_id, namespace)

    @NFVCLPublic(path="/{cluster_id}/namespace/{name}", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.create_k8s_namespace)
    def k8s_create_namespace(self, cluster_id: str, name: str, labels: dict) -> AsyncTaskResponse:
        return self.kubernetes_manager.create_k8s_namespace(cluster_id, name, labels)

    @NFVCLPublic(path="/{cluster_id}/namespace/{name}", section=K8S_SECTION, method=HttpRequestType.DELETE, sync=True, doc_by=KubernetesManager.delete_k8s_namespace)
    def k8s_delete_namespace(self, cluster_id: str, name: str) -> AsyncTaskResponse:
        return self.kubernetes_manager.delete_k8s_namespace(cluster_id, name)

    @NFVCLPublic(path="/{cluster_id}/sa/{namespace}/{user}", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.create_service_account)
    def k8s_create_service_account(self, cluster_id: str, namespace: str, user: str) -> dict:
        return self.kubernetes_manager.create_service_account(cluster_id, namespace, user)

    @NFVCLPublic(path="/{cluster_id}/sa/{namespace}/{user}", section=K8S_SECTION, method=HttpRequestType.DELETE, sync=True, doc_by=KubernetesManager.delete_service_account)
    def k8s_delete_service_account(self, cluster_id: str, namespace: str, user: str) -> dict:
        return self.kubernetes_manager.delete_service_account(cluster_id, namespace, user)

    @NFVCLPublic(path="/{cluster_id}/sa/admin/{namespace}/{username}", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.create_admin_sa_for_namespace)
    def k8s_create_admin_sa_for_namespace(self, cluster_id: str, namespace: str, username: str) -> dict:
        return self.kubernetes_manager.create_admin_sa_for_namespace(cluster_id, namespace, username)

    @NFVCLPublic(path="/{cluster_id}/sa", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_k8s_service_account)
    def k8s_get_service_account(self, cluster_id: str) -> dict:
        return self.kubernetes_manager.get_k8s_service_account(cluster_id)

    @NFVCLPublic(path="/{cluster_id}/secret/{namespace}/{user}", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.create_secret_for_sa)
    def k8s_create_secret_for_sa(self, cluster_id: str, namespace: str, user: str, secret_name: Annotated[str, "text/plain"]) -> dict:
        return self.kubernetes_manager.create_secret_for_sa(cluster_id, namespace, user, secret_name)

    @NFVCLPublic(path="/{cluster_id}/roles", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_k8s_roles)
    def k8s_get_roles(self, cluster_id: str, rolename: Optional[str] = None, namespace: Optional[str] = None) -> dict:
        role_list = self.kubernetes_manager.get_k8s_roles(cluster_id, rolename, namespace)
        return role_list.to_dict()

    @NFVCLPublic(path="/{cluster_id}/roles/admin/sa/{namespace}/{s_account}", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.give_admin_rights_to_sa)
    def k8s_give_admin_rights_to_sa(self, cluster_id: str, namespace: str, s_account: str, role_binding_name: str) -> dict:
        return self.kubernetes_manager.give_admin_rights_to_sa(cluster_id, namespace, s_account, role_binding_name)

    @NFVCLPublic(path="/{cluster_id}/roles/cluster-admin/{namespace}/{s_account}", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.give_cluster_admin_rights)
    def k8s_give_cluster_admin_rights(self, cluster_id: str, s_account: str, namespace: str, cluster_role_binding_name: str) -> dict:
        return self.kubernetes_manager.give_cluster_admin_rights(cluster_id, s_account, namespace, cluster_role_binding_name)

    @NFVCLPublic(path="/{cluster_id}/secrets", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_secrets)
    def k8s_get_secrets(self, cluster_id: str, namespace: str = "", secret_name: str = "", owner: str = "") -> dict:
        return self.kubernetes_manager.get_secrets(cluster_id, namespace, secret_name, owner)

    @NFVCLPublic(path="/{cluster_id}/user/{username}", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.create_k8s_kubectl_user, summary="Create (the user) and retrieve info for a new kubectl user")
    def k8s_create_kubectl_user(self, cluster_id: str, username: str, expire_seconds: int = 31536000) -> dict:
        return self.kubernetes_manager.create_k8s_kubectl_user(cluster_id, username, expire_seconds)

    @NFVCLPublic(path="/{cluster_id}/admission-webhook/nfvcl", section=K8S_SECTION, method=HttpRequestType.POST, sync=False, doc_by=KubernetesManager.install_nfvcl_admission_webhook, summary="Install NFVCL admission webhook")
    def k8s_install_admission_webhook(self, cluster_id: str, callback=None) -> AsyncTaskResponse:
        return self.add_task(self.kubernetes_manager.install_nfvcl_admission_webhook, cluster_id, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/admission-webhook/nfvcl", section=K8S_SECTION, method=HttpRequestType.DELETE, sync=False, doc_by=KubernetesManager.uninstall_nfvcl_admission_webhook, summary="Uninstall NFVCL admission webhook")
    def k8s_uninstall_admission_webhook(self, cluster_id: str, callback=None) -> AsyncTaskResponse:
        return self.add_task(self.kubernetes_manager.uninstall_nfvcl_admission_webhook, cluster_id, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/quota/{namespace}/{quota_name}", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.apply_resource_quota_namespace)
    def k8s_apply_resource_quota_namespace(self, cluster_id: str, namespace: str, quota_name: str, quota: K8sQuota) -> AsyncTaskResponse:
        return self.kubernetes_manager.apply_resource_quota_namespace(cluster_id, namespace, quota_name, quota)

    @NFVCLPublic(path="/{cluster_id}/quota/{namespace}", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.list_resource_quotas_namespace)
    def k8s_list_resource_quotas_namespace(self, cluster_id: str, namespace: str) -> AsyncTaskResponse:
        return self.kubernetes_manager.list_resource_quotas_namespace(cluster_id, namespace)

    @NFVCLPublic(path="/{cluster_id}/quota/{namespace}/{quota_name}", section=K8S_SECTION, method=HttpRequestType.DELETE, sync=True, doc_by=KubernetesManager.delete_resource_quota_namespace)
    def k8s_delete_resource_quota_namespace(self, cluster_id: str, namespace: str, quota_name: str) -> AsyncTaskResponse:
        return self.kubernetes_manager.delete_resource_quota_namespace(cluster_id, namespace, quota_name)

    @NFVCLPublic(path="/{cluster_id}/quota/{namespace}/{quota_name}", section=K8S_SECTION, method=HttpRequestType.PUT, sync=True, doc_by=KubernetesManager.update_resource_quota_namespace)
    def k8s_update_resource_quota_namespace(self, cluster_id: str, namespace: str, quota_name: str, quota: K8sQuota) -> AsyncTaskResponse:
        return self.kubernetes_manager.update_resource_quota_namespace(cluster_id, namespace, quota_name, quota)

    @NFVCLPublic(path="/{cluster_id}/nodes", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_nodes)
    def k8s_get_nodes(self, cluster_id: str, detailed: bool = False) -> dict:
        return self.kubernetes_manager.get_nodes(cluster_id, detailed)

    @NFVCLPublic(path="/{cluster_id}/node/{node_name}/label", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.add_label_to_k8s_node)
    def k8s_add_label_to_node(self, cluster_id: str, node_name: str, labels: Labels) -> dict:
        return self.kubernetes_manager.add_label_to_k8s_node(cluster_id, node_name, labels)

    @NFVCLPublic(path="/{cluster_id}/node/{node_name}/label", section=K8S_SECTION, method=HttpRequestType.DELETE, sync=True, doc_by=KubernetesManager.delete_label_from_k8s_node)
    def k8s_delete_label_from_node(self, cluster_id: str, node_name: str, labels: Labels) -> dict:
        return self.kubernetes_manager.delete_label_from_k8s_node(cluster_id, node_name, labels)

    @NFVCLPublic(path="/{cluster_id}/deployments", section=K8S_SECTION, method=HttpRequestType.GET, sync=True, doc_by=KubernetesManager.get_deployment)
    def k8s_get_deployment(self, cluster_id: str, namespace: str, detailed: bool = False) -> dict:
        return self.kubernetes_manager.get_deployment(cluster_id, namespace, detailed)

    @NFVCLPublic(path="/{cluster_id}/deployment/label", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.add_label_to_k8s_deployment)
    def k8s_add_label_to_deployment(self, cluster_id: str, namespace: str, deployment_name: str, labels: Labels) -> dict:
        return self.kubernetes_manager.add_label_to_k8s_deployment(cluster_id, namespace, deployment_name, labels)

    @NFVCLPublic(path="/{cluster_id}/deployment/{namespace}/{deployment_name}/label", section=K8S_SECTION, method=HttpRequestType.DELETE, sync=True, doc_by=KubernetesManager.delete_label_from_k8s_deployment)
    def k8s_delete_label_from_deployment(self, cluster_id: str, namespace: str, deployment_name: str, labels: Labels) -> dict:
        return self.kubernetes_manager.delete_label_from_k8s_deployment(cluster_id, namespace, deployment_name, labels)

    @NFVCLPublic(path="/{cluster_id}/deployment/scale", section=K8S_SECTION, method=HttpRequestType.POST, sync=True, doc_by=KubernetesManager.scale_k8s_deployment)
    def k8s_scale_deployment(self, cluster_id: str, namespace: str, deployment_name: str, replica_number: int) -> dict:
        return self.kubernetes_manager.scale_k8s_deployment(cluster_id, namespace, deployment_name, replica_number)

    ############# User management #############

    @NFVCLPublic(path="/{username}", section=USER_SECTION, method=HttpRequestType.GET, sync=True)
    def get_user(self, username: str) -> UserNoConfidence:
        return self.user_manager.get_censored_user_by_username(username)

    @NFVCLPublic(path="/", section=USER_SECTION, method=HttpRequestType.GET, sync=True)
    def get_user_list(self) -> List[UserNoConfidence]:
        return self.user_manager.get_censored_users()

    @NFVCLPublic(path="/", section=USER_SECTION, method=HttpRequestType.POST, sync=True)
    def create_user(self, user: UserCreateREST) -> UserNoConfidence:
        return self.user_manager.add_user_rest(user)

    @NFVCLPublic(path="/{username}", section=USER_SECTION, method=HttpRequestType.DELETE, sync=True)
    def delete_user(self, username: str) -> UserNoConfidence:
        return self.user_manager.delete_user(username)

def configure_injection(nfvcl_config: NFVCLConfigModel):
    container = NFVCLContainer()
    container.config.from_pydantic(nfvcl_config)
    container.init_resources()
    container.wire(modules=[__name__, "nfvcl_core.managers", "nfvcl_core.managers.getters"])
    # register_loader_containers(Container)
