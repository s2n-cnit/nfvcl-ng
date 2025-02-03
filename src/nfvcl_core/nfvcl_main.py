import inspect
import threading
from enum import Enum
from functools import partial
from typing import Callable, Dict, List, Any, Optional, Annotated

import urllib3
from dependency_injector.wiring import Provide
from fastapi import HTTPException
from pydantic import Field

from nfvcl.blueprints_ng.pdu_configurators.implementations import register_pdu_implementations
from nfvcl.models.k8s.common_k8s_model import Labels
from nfvcl.models.k8s.plugin_k8s_model import K8sPluginsToInstall
from nfvcl.models.k8s.topology_k8s_model import TopologyK8sModel, K8sQuota
from nfvcl_core import global_ref
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, BlueprintModule, BlueprintDay2Route
from nfvcl_core.config import NFVCLConfigModel, load_nfvcl_config
from nfvcl_core.containers import NFVCLContainer
from nfvcl_core.managers import TopologyManager, BlueprintManager, TaskManager, PerformanceManager, EventManager
from nfvcl_core.managers.blueprint_manager import PreWorkCallbackResponse
from nfvcl_core.managers.kubernetes_manager import KubernetesManager
from nfvcl_core.managers.pdu_manager import PDUManager
from nfvcl_core.managers.user_manager import UserManager
from nfvcl_core.models.base_model import NFVCLBaseModel
from nfvcl_core.models.blueprints.blueprint import BlueprintNGCreateModel
from nfvcl_core.models.network import PduModel, NetworkModel, RouterModel
from nfvcl_core.models.performance import BlueprintPerformance
from nfvcl_core.models.prometheus.prometheus_model import PrometheusServerModel
from nfvcl_core.models.response_model import OssCompliantResponse
from nfvcl_core.models.task import NFVCLTaskResult, NFVCLTask, NFVCLTaskStatus, NFVCLTaskStatusType
from nfvcl_core.models.topology_models import TopologyModel
from nfvcl_core.models.vim import VimModel
from nfvcl_core.public_methods_description import GET_PROM_SRV_SUMMARY, GET_PROM_SRV_DESCRIPTION, GET_PROM_LIST_SRV_SUMMARY, GET_PROM_LIST_SRV_DESCRIPTION, DEL_PROM_SRV_SUMMARY, DEL_PROM_SRV_DESCRIPTION, UPD_PROM_SRV_SUMMARY, UPD_PROM_SRV_DESCRIPTION, ADD_PROM_SRV_DESCRIPTION, ADD_PROM_SRV_SUMMARY, UPD_K8SCLUSTER_SUMMARY, UPD_K8SCLUSTER_DESCRIPTION, ADD_EXTERNAL_K8SCLUSTER_SUMMARY, ADD_EXTERNAL_K8SCLUSTER
from nfvcl_core.utils.log import create_logger
from nfvcl_core.utils.openstack.openstack_utils import check_openstack_instances


def callback_function(event: threading.Event, namespace: Dict, msg: NFVCLTaskResult):
    namespace["msg"] = msg
    event.set()


def pre_work_callback_function(event: threading.Event, namespace: Dict, msg: PreWorkCallbackResponse):
    namespace["msg"] = msg
    event.set()


class NFVCLPublicSectionModel(NFVCLBaseModel):
    name: str = Field()
    description: str = Field()
    path: str = Field()


class NFVCLPublicMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class NFVCLPublicModel(NFVCLBaseModel):
    path: str = Field()
    method: str = Field()
    section: NFVCLPublicSectionModel = Field()
    sync: bool = Field(default=False)
    summary: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)


class NFVCLPublic:
    order: int = 0

    def __init__(self, path: str, method: str, section: NFVCLPublicSectionModel, sync: bool = False, doc_by: Optional[Callable] = None, summary: Optional[str] = None, description: Optional[str] = None):
        self.path = path
        self.method = method
        self.section = section
        self.sync = sync
        self.doc_override = doc_by.__doc__ if doc_by else None
        self.summary = summary
        self.description = description

    def __call__(self, func):
        if self.doc_override:
            func.__doc__ = self.doc_override
        func.nfvcl_public = NFVCLPublicModel(path=self.path, method=self.method, section=self.section, sync=self.sync, summary=self.summary, description=self.description)
        func.order = NFVCLPublic.order
        NFVCLPublic.order += 1
        return func


class NFVCL:
    TOPOLOGY_SECTION = NFVCLPublicSectionModel(name="Topology", description="Operations related to the topology", path="/v1/topology")
    BLUEPRINTS_SECTION = NFVCLPublicSectionModel(name="Blueprints", description="Operations related to the blueprints", path="/nfvcl/v2/api/blue")
    PERFORMANCE_SECTION = NFVCLPublicSectionModel(name="Performances", description="Operations related to the performance metrics", path="/performance/blue")
    K8S_SECTION = NFVCLPublicSectionModel(name="Kubernetes cluster management", description="Operations related to kubernetes clusters", path="/k8s")
    UTILS_SECTION = NFVCLPublicSectionModel(name="Utils", description="Utils", path="/v2/utils")
    USER_SECTION = NFVCLPublicSectionModel(name="Users", description="User management", path="/v2/users")

    def __init__(
        self,
        config: NFVCLConfigModel = Provide[NFVCLContainer.config],
        task_manager: TaskManager = Provide[NFVCLContainer.task_manager],
        event_manager: EventManager = Provide[NFVCLContainer.event_manager],
        topology_manager: TopologyManager = Provide[NFVCLContainer.topology_manager],
        blueprint_manager: BlueprintManager = Provide[NFVCLContainer.blueprint_manager],
        performance_manager: PerformanceManager = Provide[NFVCLContainer.performance_manager],
        pdu_manager: PDUManager = Provide[NFVCLContainer.pdu_manager],
        kubernetes_manager: KubernetesManager = Provide[NFVCLContainer.kubernetes_manager],
        user_manager: UserManager = Provide[NFVCLContainer.user_manager],
    ):
        self.logger = create_logger(self.__class__.__name__)

        global_ref.nfvcl_config = NFVCLConfigModel.model_validate(config)

        self.topology_manager = topology_manager
        self.blueprint_manager = blueprint_manager
        self.performance_manager = performance_manager
        self.kubernetes_manager = kubernetes_manager
        self.task_manager = task_manager
        self.event_manager = event_manager
        self.user_manager = user_manager

        urllib3.disable_warnings()

        register_pdu_implementations(pdu_manager)

        self.blueprint_manager.load()
        self.performance_manager.load()
        self.user_manager.load()


        # TODO rework plugin loading
        from nfvcl_core.plugins.plugin import NFVCLPlugin
        from nfvcl_horse.horse import NFVCLHorsePlugin

        self.plugins: List[NFVCLPlugin] = [NFVCLHorsePlugin(self)]

        for plugin in self.plugins:
            plugin.load()



    # def vim_checks(self):
    #     # TODO maybe this should be moved somewere else?
    #     # TODO better handling if the topology is not present
    #     try:
    #         topology = self.topology_manager.get_topology()
    #         vim_list = topology.get_vims()
    #         vim_list = list(filter(lambda x: x.vim_type == "openstack", vim_list))
    #         err_list = check_openstack_instances(topology, vim_list)
    #         for err in err_list:
    #             self.logger.error(f"Error checking VIM: {err.name}")
    #     except Exception as e:
    #         self.logger.error(f"Error checking VIMs: {e}")

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

    def _add_task_async(self, function: Callable, *args, **kwargs) -> OssCompliantResponse:
        callback: Optional[Callable] = kwargs.pop("callback", None)
        # check if the callable function has a pre_work_callback parameter
        function_args = inspect.getfullargspec(function).args
        event: Optional[threading.Event] = None
        namespace = {}

        if "pre_work_callback" in function_args:
            print("setting pre_work_callback")
            event = threading.Event()
            kwargs["pre_work_callback"] = partial(pre_work_callback_function, event, namespace)

        task_id = self.task_manager.add_task(NFVCLTask(function, callback, *args, **kwargs))

        async_response: OssCompliantResponse

        if "pre_work_callback" in function_args and event:
            event.wait()
            pre_work_callback_response: PreWorkCallbackResponse = namespace["msg"]
            async_response = pre_work_callback_response.async_return
        else:
            async_response = OssCompliantResponse(detail="Operation submitted")

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

    @NFVCLPublic(path="/get_task_status", section=UTILS_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_task_status(self, task_id: str) -> NFVCLTaskStatus:
        """
        Get the status of a task given its task_id

        Warnings:
            If NFVCL is restarted the task_id will be lost and the task will not be found
        Args:
            task_id: ID of the task to get the status of

        Returns: NFVCLTaskStatus, the "status" field can be "running" or "done"
        """
        if task_id not in self.task_manager.task_history:
            raise ValueError("Task not found")
        if task_id in self.task_manager.task_history:
            task = self.task_manager.task_history[task_id]
            if task.result is None:
                return NFVCLTaskStatus(task_id=task_id, status=NFVCLTaskStatusType.RUNNING)
            else:
                return NFVCLTaskStatus(task_id=task_id, status=NFVCLTaskStatusType.DONE, result=task.result.result, error=task.result.error, exception=str(task.result.exception) if task.result.exception else None)

    ############# Topology #############

    @NFVCLPublic(path="", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_topology(self, callback=None) -> TopologyModel:
        """
        Get information regarding the managed topology
        """
        return self.add_task(self.topology_manager.get_topology, callback=callback)

    @NFVCLPublic(path="", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.POST)
    def create_topology(self, topology: TopologyModel, callback=None):
        """
        Create the topology
        """
        return self.add_task(self.topology_manager.create_topology, topology, callback=callback)

    @NFVCLPublic(path="", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.DELETE)
    def delete_topology(self, callback=None):
        return self.add_task(self.topology_manager.delete_topology, callback=callback)

    @NFVCLPublic(path="/vim/{vim_id}", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_vim(self, vim_id: str, callback=None) -> VimModel:
        return self.add_task(self.topology_manager.get_vim, vim_id, callback=callback)

    @NFVCLPublic(path="/vim", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.POST)
    def create_vim(self, vim: VimModel, callback=None):
        return self.add_task(self.topology_manager.create_vim, vim, callback=callback)

    @NFVCLPublic(path="/vim/update", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.PUT)
    def update_vim(self, vim: VimModel, callback=None):
        return self.add_task(self.topology_manager.update_vim, vim, callback=callback)

    @NFVCLPublic(path="/vim/{vim_id}", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.DELETE)
    def delete_vim(self, vim_id: str, callback=None):
        return self.add_task(self.topology_manager.delete_vim, vim_id, callback=callback)

    @NFVCLPublic(path="/network/{network_id}", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_network(self, network_id: str, callback=None) -> NetworkModel:
        return self.add_task(self.topology_manager.get_network, network_id, callback=callback)

    @NFVCLPublic(path="/network", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.POST)
    def create_network(self, network: NetworkModel, callback=None):
        return self.add_task(self.topology_manager.create_network, network, callback=callback)

    @NFVCLPublic(path="/network/{network_id}", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.DELETE)
    def delete_network(self, network_id: str, callback=None):
        return self.add_task(self.topology_manager.delete_network, network_id, callback=callback)

    @NFVCLPublic(path="/router/{router_id}", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_router(self, network_id: str, callback=None) -> RouterModel:
        return self.add_task(self.topology_manager.get_router, network_id, callback=callback)

    @NFVCLPublic(path="/router", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.POST)
    def create_router(self, router: RouterModel, callback=None) -> RouterModel:
        return self.add_task(self.topology_manager.create_router, router, callback=callback)

    @NFVCLPublic(path="/router/{router_id}", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.DELETE)
    def delete_router(self, router_id: str, callback=None) -> RouterModel:
        return self.add_task(self.topology_manager.delete_router, router_id, callback=callback)

    @NFVCLPublic(path="/pdus", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_pdus(self, callback=None) -> List[PduModel]:
        return self.add_task(self.topology_manager.get_pdus, callback=callback)

    @NFVCLPublic(path="/pdu/{pdu_id}", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_pdu(self, pdu_id: str, callback=None) -> PduModel:
        return self.add_task(self.topology_manager.get_pdu, pdu_id, callback=callback)

    @NFVCLPublic(path="/pdu", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.POST)
    def create_pdu(self, pdu: PduModel, callback=None):
        return self.add_task(self.topology_manager.create_pdu, pdu, callback=callback)

    @NFVCLPublic(path="/pdu/{pdu_id}", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.DELETE)
    def delete_pdu(self, pdu_id: str, callback=None):
        return self.add_task(self.topology_manager.delete_pdu, pdu_id, callback=callback)

    # @NFVCLPublic(path="/pdu/{pdu_id}/force_unlock", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.POST)
    # def force_unlock_pdu(self, pdu_id: str, callback=None):
    #     return self._add_task(self._topology_manager.force_unlock_pdu, pdu_id, callback=callback)

    @NFVCLPublic(path="/kubernetes", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_kubernetes_list(self, callback=None) -> List[TopologyK8sModel]:
        return self.add_task(self.topology_manager.get_kubernetes_list, callback=callback)

    @NFVCLPublic(path="/kubernetes/{cluster_id}", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_kubernetes(self, cluster_id: str, callback=None) -> TopologyK8sModel:
        return self.add_task(self.topology_manager.get_k8s_cluster_by_id, cluster_id, callback=callback)

    @NFVCLPublic(
        path="/kubernetes_external",
        section=TOPOLOGY_SECTION,
        method=NFVCLPublicMethod.POST,
        summary=ADD_EXTERNAL_K8SCLUSTER_SUMMARY,
        description=ADD_EXTERNAL_K8SCLUSTER
    )
    def create_kubernetes_external(self, kubernetes_model: TopologyK8sModel, callback=None):
        kubernetes_model.provided_by = 'external'
        return self.add_task(self.topology_manager.add_kubernetes, kubernetes_model, callback=callback)

    @NFVCLPublic(
        path="/kubernetes/update",
        section=TOPOLOGY_SECTION,
        method=NFVCLPublicMethod.PUT,
        summary=UPD_K8SCLUSTER_SUMMARY,
        description=UPD_K8SCLUSTER_DESCRIPTION
    )
    def update_kubernetes(self, cluster: TopologyK8sModel, callback=None):
        return self.add_task(self.topology_manager.update_kubernetes, cluster, callback=callback)

    @NFVCLPublic(path="/kubernetes/{cluster_id}", section=TOPOLOGY_SECTION, method=NFVCLPublicMethod.DELETE)
    def delete_kubernetes(self, cluster_id: str, callback=None):
        return self.add_task(self.topology_manager.delete_kubernetes, cluster_id, callback=callback)

    @NFVCLPublic(
        path="/prometheus",
        section=TOPOLOGY_SECTION,
        method=NFVCLPublicMethod.GET,
        sync=True,
        summary=GET_PROM_LIST_SRV_SUMMARY,
        description=GET_PROM_LIST_SRV_DESCRIPTION
    )
    def get_prometheus_list(self, callback=None) -> List[PrometheusServerModel]:
        return self.add_task(self.topology_manager.get_prometheus_list, callback=callback)

    @NFVCLPublic(
        path="/prometheus/{prometheus_id}",
        section=TOPOLOGY_SECTION,
        method=NFVCLPublicMethod.GET,
        sync=True,
        summary=GET_PROM_SRV_SUMMARY,
        description=GET_PROM_SRV_DESCRIPTION
    )
    def get_prometheus(self, prometheus_id: str, callback=None) -> PrometheusServerModel:
        return self.add_task(self.topology_manager.get_prometheus, prometheus_id, callback=callback)

    @NFVCLPublic(
        path="/prometheus",
        section=TOPOLOGY_SECTION,
        method=NFVCLPublicMethod.POST,
        summary=ADD_PROM_SRV_SUMMARY,
        description=ADD_PROM_SRV_DESCRIPTION
    )
    def create_prometheus(self, prometheus_model: PrometheusServerModel, callback=None):
        return self.add_task(self.topology_manager.add_prometheus, prometheus_model, callback=callback)

    @NFVCLPublic(
        path="/prometheus/{prometheus_id}",
        section=TOPOLOGY_SECTION,
        method=NFVCLPublicMethod.PUT,
        summary=UPD_PROM_SRV_SUMMARY,
        description=UPD_PROM_SRV_DESCRIPTION
    )
    def update_prometheus(self, prometheus_model: PrometheusServerModel, callback=None):
        return self.add_task(self.topology_manager.update_prometheus, prometheus_model, callback=callback)

    @NFVCLPublic(
        path="/prometheus/{prometheus_id}",
        section=TOPOLOGY_SECTION,
        method=NFVCLPublicMethod.DELETE,
        summary=DEL_PROM_SRV_SUMMARY,
        description=DEL_PROM_SRV_DESCRIPTION
    )
    def delete_prometheus(self, prometheus_id: str, callback=None):
        return self.add_task(self.topology_manager.delete_prometheus, prometheus_id, callback=callback)

    ############# Blueprints #############

    @NFVCLPublic(path="", section=BLUEPRINTS_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_blueprints(self, blue_type: str = None, detailed: bool = False, callback=None) -> List[dict]:
        return self.add_task(self.blueprint_manager.get_blueprint_summary_list, blue_type, detailed, callback=callback)

    @NFVCLPublic(path="/{blueprint_id}", section=BLUEPRINTS_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_blueprint(self, blueprint_id: str = None, detailed: bool = False, callback=None) -> dict:
        return self.add_task(self.blueprint_manager.get_blueprint_summary_by_id, blueprint_id, detailed, callback=callback)

    # @NFVCLPublic(path="", section=BLUEPRINTS_SECTION, method=NFVCLPublicMethod.POST)
    def create_blueprint(self, blue_type: str, msg: BlueprintNGCreateModel, callback=None):
        return self.add_task(self.blueprint_manager.create_blueprint, blue_type, msg, callback=callback)

    # @NFVCLPublic(path="", section=BLUEPRINTS_SECTION, method=NFVCLPublicMethod.PUT)
    def update_blueprint(self, blue_id: str, day2_path: str, msg: Any, callback=None):
        return self.add_task(self.blueprint_manager.update_blueprint, blue_id, day2_path, msg, callback=callback)

    # @NFVCLPublic(path="/get_from_blueprint", section=BLUEPRINTS_SECTION, method=NFVCLPublicMethod.GET)
    def get_from_blueprint(self, blue_id: str, day2_path: str, callback=None) -> Any:
        return self.add_task(self.blueprint_manager.get_from_blueprint, blue_id, day2_path, callback=callback)

    @NFVCLPublic(path="/{blueprint_id}", section=BLUEPRINTS_SECTION, method=NFVCLPublicMethod.DELETE)
    def delete_blueprint(self, blueprint_id: str, callback=None):
        return self.add_task(self.blueprint_manager.delete_blueprint, blueprint_id, callback=callback)

    @NFVCLPublic(path="/all/blue", section=BLUEPRINTS_SECTION, method=NFVCLPublicMethod.DELETE)
    def delete_all_blueprints(self, callback=None):
        return self.add_task(self.blueprint_manager.delete_all_blueprints, callback=callback)

    @NFVCLPublic(path="/protect/{blueprint_id}", section=BLUEPRINTS_SECTION, method=NFVCLPublicMethod.PATCH, sync=True)
    def protect_blueprint(self, blueprint_id: str, protect: bool, callback=None) -> dict:
        return self.add_task(self.blueprint_manager.protect_blueprint, blueprint_id, protect, callback=callback)

    ############# Performance #############

    @NFVCLPublic(path="/{blueprint_id}", section=PERFORMANCE_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_performance(self, blueprint_id: str, callback=None) -> BlueprintPerformance:
        return self.add_task(self.performance_manager.get_blue_performance, blueprint_id, callback=callback)

    # @NFVCLPublic(path="/{blueprint_id}", section=PERFORMANCE_SECTION, method=NFVCLPublicMethod.DELETE)
    # def delete_performance(self, blueprint_id: str, callback=None):
    #     return self._add_task(self._performance_manager.delete_performance, blueprint_id, callback=callback)

    ############# Kubernetes cluster management #############

    @NFVCLPublic(path="/{cluster_id}/plugins", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_k8s_installed_plugins)
    def k8s_get_installed_plugins(self, cluster_id: str, callback=None) -> List[str]:
        try:
            return self.add_task(self.kubernetes_manager.get_k8s_installed_plugins, cluster_id, callback=callback)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) # TODO do not return exception here


    @NFVCLPublic(path="/{cluster_id}/plugins", section=K8S_SECTION, method=NFVCLPublicMethod.PUT, sync=False, doc_by=KubernetesManager.install_plugins)
    def k8s_install_plugin(self, cluster_id: str, plugin_name: K8sPluginsToInstall, callback=None) -> OssCompliantResponse:
        return self.add_task(self.kubernetes_manager.install_plugins, cluster_id, plugin_name, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/yaml", section=K8S_SECTION, method=NFVCLPublicMethod.PUT, sync=False, doc_by=KubernetesManager.apply_to_k8s)
    def k8s_apply_yaml(self, cluster_id: str, yaml: Annotated[str, "application/yaml"], callback=None) -> OssCompliantResponse:
        return self.add_task(self.kubernetes_manager.apply_to_k8s, cluster_id, yaml, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/cidr", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_k8s_cidr)
    def k8s_get_cluster_cidr(self, cluster_id: str, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.get_k8s_cidr, cluster_id, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/ipaddresspools", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_k8s_ipaddress_pools)
    def k8s_get_ipaddresspools(self, cluster_id: str, callback=None) -> List[str]:
        return self.add_task(self.kubernetes_manager.get_k8s_ipaddress_pools, cluster_id, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/storageclasses", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_k8s_storage_classes)
    def k8s_get_storage_classes(self, cluster_id: str, callback=None) -> List[str]:
        dsc = self.add_task(self.kubernetes_manager.get_k8s_storage_classes, cluster_id, callback=callback)
        if dsc is not None:
            return dsc
        else:
            raise HTTPException(status_code=404, detail="No default storage class found") # TODO do not return exception here

    @NFVCLPublic(path="/{cluster_id}/defaultstorageclasses", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_k8s_default_storage_class)
    def k8s_get_default_storage_classes(self, cluster_id: str, callback=None) -> str:
        return self.add_task(self.kubernetes_manager.get_k8s_default_storage_class, cluster_id, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/pods", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_k8s_pods)
    def k8s_get_pods(self, cluster_id: str, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.get_k8s_pods, cluster_id, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/namespaces", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_k8s_namespace_list)
    def k8s_get_namespace_list(self, cluster_id: str, namespace: Optional[str] = None, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.get_k8s_namespace_list, cluster_id, namespace, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/namespace/{name}", section=K8S_SECTION, method=NFVCLPublicMethod.PUT, sync=True, doc_by=KubernetesManager.create_k8s_namespace)
    def k8s_create_namespace(self, cluster_id: str, name: str, labels: dict, callback=None) -> OssCompliantResponse:
        return self.add_task(self.kubernetes_manager.create_k8s_namespace, cluster_id, name, labels, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/namespace/{name}", section=K8S_SECTION, method=NFVCLPublicMethod.DELETE, sync=True, doc_by=KubernetesManager.delete_k8s_namespace)
    def k8s_delete_namespace(self, cluster_id: str, name: str, callback=None) -> OssCompliantResponse:
        return self.add_task(self.kubernetes_manager.delete_k8s_namespace, cluster_id, name, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/sa", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_k8s_service_account)
    def k8s_get_service_account(self, cluster_id: str, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.get_k8s_service_account, cluster_id, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/roles", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_k8s_roles)
    def k8s_get_roles(self, cluster_id: str, rolename: Optional[str] = None, namespace: Optional[str] = None, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.get_k8s_roles, cluster_id, rolename, namespace, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/roles/admin/sa/{namespace}/{s_account}", section=K8S_SECTION, method=NFVCLPublicMethod.POST, sync=True, doc_by=KubernetesManager.give_admin_rights_to_sa)
    def k8s_give_admin_rights_to_sa(self, cluster_id: str, namespace: str, s_account: str, role_binding_name: Annotated[str, "text/plain"], callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.give_admin_rights_to_sa, cluster_id, namespace, s_account, role_binding_name, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/roles/admin/{namespace}/{user}", section=K8S_SECTION, method=NFVCLPublicMethod.POST, sync=True, doc_by=KubernetesManager.give_admin_rights_to_user_namespaced)
    def k8s_give_admin_rights_to_user_namespaced(self, cluster_id: str, namespace: str, user: str, role_binding_name: Annotated[str, "text/plain"], callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.give_admin_rights_to_user_namespaced, cluster_id, namespace, user, role_binding_name, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/roles/cluster-admin/{user}", section=K8S_SECTION, method=NFVCLPublicMethod.POST, sync=True, doc_by=KubernetesManager.give_cluster_admin_rights)
    def k8s_give_cluster_admin_rights(self, cluster_id: str, user: str, cluster_role_binding_name: Annotated[str, "text/plain"], callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.give_cluster_admin_rights, cluster_id, user, cluster_role_binding_name, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/sa/{namespace}/{user}", section=K8S_SECTION, method=NFVCLPublicMethod.PUT, sync=True, doc_by=KubernetesManager.create_service_account)
    def k8s_create_service_account(self, cluster_id: str, namespace: str, user: str, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.create_service_account, cluster_id, namespace, user, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/secret/{namespace}/{user}", section=K8S_SECTION, method=NFVCLPublicMethod.POST, sync=True, doc_by=KubernetesManager.create_secret_for_sa)
    def k8s_create_secret_for_sa(self, cluster_id: str, namespace: str, user: str, secret_name: Annotated[str, "text/plain"], callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.create_secret_for_sa, cluster_id, namespace, user, secret_name, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/secrets", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_secrets)
    def k8s_get_secrets(self, cluster_id: str, namespace: str = "", secret_name: str = "", owner: str = "", callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.get_secrets, cluster_id, namespace, secret_name, owner, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/sa/{namespace}/{username}", section=K8S_SECTION, method=NFVCLPublicMethod.POST, sync=True, doc_by=KubernetesManager.create_admin_sa_for_namespace)
    def k8s_create_admin_sa_for_namespace(self, cluster_id: str, namespace: str, username: str, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.create_admin_sa_for_namespace, cluster_id, namespace, username, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/user/{username}", section=K8S_SECTION, method=NFVCLPublicMethod.POST, sync=True, doc_by=KubernetesManager.create_k8s_kubectl_user, summary="Create (the user) and retrieve info for a new kubectl user")
    def k8s_create_kubectl_user(self, cluster_id: str, username: str, expire_seconds: int = 31536000, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.create_k8s_kubectl_user, cluster_id, username, expire_seconds, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/quota/{namespace}/{quota_name}", section=K8S_SECTION, method=NFVCLPublicMethod.POST, sync=True, doc_by=KubernetesManager.apply_resource_quota_namespace)
    def k8s_apply_resource_quota_namespace(self, cluster_id: str, namespace: str, quota_name: str, quota: K8sQuota, callback=None) -> OssCompliantResponse:
        return self.add_task(self.kubernetes_manager.apply_resource_quota_namespace, cluster_id, namespace, quota_name, quota, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/nodes", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_nodes)
    def k8s_get_nodes(self, cluster_id: str, detailed: bool = False, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.get_nodes, cluster_id, detailed, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/node/{node_name}", section=K8S_SECTION, method=NFVCLPublicMethod.POST, sync=True, doc_by=KubernetesManager.add_label_to_k8s_node)
    def k8s_add_label_to_node(self, cluster_id: str, node_name: str, labels: Labels, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.add_label_to_k8s_node, cluster_id, node_name, labels, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/deployments", section=K8S_SECTION, method=NFVCLPublicMethod.GET, sync=True, doc_by=KubernetesManager.get_deployment)
    def k8s_get_deployment(self, cluster_id: str, namespace: str, detailed: bool = False, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.get_deployment, cluster_id, namespace, detailed, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/deployment/label", section=K8S_SECTION, method=NFVCLPublicMethod.POST, sync=True, doc_by=KubernetesManager.add_label_to_k8s_deployment)
    def k8s_add_label_to_deployment(self, cluster_id: str, namespace: str, deployment_name: str, labels: Labels, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.add_label_to_k8s_deployment, cluster_id, namespace, deployment_name, labels, callback=callback)

    @NFVCLPublic(path="/{cluster_id}/deployment/scale", section=K8S_SECTION, method=NFVCLPublicMethod.POST, sync=True, doc_by=KubernetesManager.scale_k8s_deployment)
    def k8s_scale_deployment(self, cluster_id: str, namespace: str, deployment_name: str, replica_number: int, callback=None) -> dict:
        return self.add_task(self.kubernetes_manager.scale_k8s_deployment, cluster_id, namespace, deployment_name, replica_number, callback=callback)

    ############# User management #############


def configure_injection(config_path: Optional[str] = None):
    container = NFVCLContainer()
    container.config.from_pydantic(load_nfvcl_config(path=config_path))
    container.init_resources()
    container.wire(modules=[__name__, "nfvcl_core.managers"])
    # register_loader_containers(Container)
