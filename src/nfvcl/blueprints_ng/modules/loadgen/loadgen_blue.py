import json
import uuid
from typing import Optional, List, Dict

import requests  # type: ignore[import-untyped]
from pydantic import Field

from nfvcl.blueprints_ng.modules.loadgen.loadgen_rest import LoadRequest
from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_core.blueprints.blueprint_ng import BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type, day2_function
from nfvcl_core_models.blueprints.blueprint import BlueprintNGCreateModel, BlueprintNGException, BlueprintNGState
from nfvcl_core_models.resources import (
    HelmChartResource,
    VmResource,
    VmResourceImage,
    VmResourceAnsibleConfiguration,
    VmResourceFlavor,
)

class LoadGenPerformanceTraceItem(NFVCLBaseModel):
    seq_number: int
    areas: Dict[str, LoadRequest]

class LoadGenPerformanceTrace(NFVCLBaseModel):
    """Describe a sequence of load requests grouped by area ID."""
    trace: List[LoadGenPerformanceTraceItem] = Field()


class LoadGenPerformanceTraceSequence(NFVCLBaseModel):
    """Identify a performance trace item by its sequence number."""
    seq_number: int = Field()


class LoadGenVMCreateModel(BlueprintNGCreateModel):
    area_id: int = Field()
    mgmt_net: str = Field()
    data_nets: List[str] = Field(default_factory=list)
    flavor: VmResourceFlavor = Field(
        default=VmResourceFlavor(),
        description="Optional flavors, if flavor.name is specified it will try to use this the existing flavor",
    )
    load: LoadRequest = Field(default=LoadRequest())

class LoadGenK8SCreateModel(BlueprintNGCreateModel):
    area_id: int
    load: LoadRequest = Field(default=LoadRequest())

class LoadGenCreateModel(BlueprintNGCreateModel):
    vms: List[LoadGenVMCreateModel] = Field(default_factory=list)
    k8s: List[LoadGenK8SCreateModel] = Field(default_factory=list)

UBU24_IMAGE_NAME = "ubuntu-lab-24-v0.1.9"
UBU24_BASE_IMAGE_URL = "https://images.tnt-lab.unige.it/ubuntu-lab/ubuntu-lab-v0.1.9-ubuntu2404.qcow2"
LOAD_GEN_DEB_URL = "https://gitlab.tnt-lab.unige.it/api/v4/projects/78/packages/generic/load-gen/v0-0-2/load-gen_v0-0-2_ubuntu24.04_amd64.deb"

class LoadGenVmConfigurator(VmResourceAnsibleConfiguration):
    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook LoadCoreAgentVmConfigurator")
        ansible_builder.add_shell_task(f"wget {LOAD_GEN_DEB_URL}")
        ansible_builder.add_shell_task(f"dpkg -i {LOAD_GEN_DEB_URL.split("/")[-1]}")
        # Service should already be enabled and started by deb postinstall script
        return ansible_builder.build()


class LoadGenBlueprintNGState(BlueprintNGState):
    vms: Dict[str, VmResource] = Field(default_factory=dict)
    vms_configurator: Dict[str, LoadGenVmConfigurator] = Field(default_factory=dict)
    k8s_helm_charts: Dict[str, HelmChartResource] = Field(default_factory=dict)
    performance_trace: Optional[LoadGenPerformanceTrace] = Field(default=None)
    performance_trace_replica: Optional[int] = Field(default=None)


@blueprint_type("loadgen")
class LoadGenBlueprintNG(BlueprintNG[LoadGenBlueprintNGState, LoadGenCreateModel]):
    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = LoadGenBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: LoadGenCreateModel):
        """
        This docstring for the create function will be shown on Swagger
        """
        super().create(create_model)
        self.logger.info("Starting creation of LoadGen blueprint")

        for vm in create_model.vms:
            self.state.vms[str(vm.area_id)] = VmResource(
                area=vm.area_id,
                resource_group=self.id,
                name=f"{self.id}_VM_LOADGEN_{vm.area_id}",
                image=VmResourceImage(
                    name=UBU24_IMAGE_NAME, url=UBU24_BASE_IMAGE_URL, check_sha512sum=False
                ),
                flavor=vm.flavor,
                username="ubuntu",
                password="ubuntu",
                management_network=vm.mgmt_net,
                additional_networks=vm.data_nets,
            )

            # Registering VM for Ubuntu
            self.register_resource(self.state.vms[str(vm.area_id)])
            # Creating VM
            self.provider.create_vm(self.state.vms[str(vm.area_id)])
            # No need for configuration, at least for now.

            self.state.vms_configurator[str(vm.area_id)] = LoadGenVmConfigurator(vm_resource=self.state.vms[str(vm.area_id)], resource_group=self.id)
            self.register_resource(self.state.vms_configurator[str(vm.area_id)])
            self.provider.configure_vm(self.state.vms_configurator[str(vm.area_id)])

        for k8s in create_model.k8s:
            area_id = str(k8s.area_id)
            helm_chart = HelmChartResource(
                area=k8s.area_id,
                name=f"loadgen-{k8s.area_id}",
                chart="helm_charts/charts/load-gen-0.1.0.tgz",
                chart_as_path=True,
                namespace=self.id,
                resource_group=self.id,
            )
            self.state.k8s_helm_charts[area_id] = helm_chart
            self.register_resource(helm_chart)
            self.provider.install_helm_chart(helm_chart, {})
            self._apply_k8s_load(k8s.area_id, helm_chart, k8s.load)

    @day2_function("/load_performance_trace", [HttpRequestType.PUT])
    def load_performance_trace(self, model: LoadGenPerformanceTrace) -> None:
        if model.trace:
            area_ids = set(model.trace[0].areas)
            if any(set(trace_item.areas) != area_ids for trace_item in model.trace[1:]):
                raise BlueprintNGException("All trace items must contain the same areas")

            sequence_numbers = [trace_item.seq_number for trace_item in model.trace]
            if len(sequence_numbers) != len(set(sequence_numbers)):
                raise BlueprintNGException("Performance trace sequence numbers must be unique")
        self.state.performance_trace = model
        self.state.performance_trace_replica = None

    @day2_function("/start_trace_replica", [HttpRequestType.PUT])
    def start_trace_replica(self) -> None:
        if self.state.performance_trace is None or not self.state.performance_trace.trace:
            raise BlueprintNGException("No performance trace has been loaded")
        self._apply_trace_replica(0)
        self.state.performance_trace_replica = 0

    @day2_function("/stop_trace_replica", [HttpRequestType.PUT])
    def stop_trace_replica(self) -> None:
        for area_id, vm in (self.state.vms or {}).items():
            self._apply_load(int(area_id), vm, LoadRequest())
        for area_id, helm_chart in (self.state.k8s_helm_charts or {}).items():
            self._apply_k8s_load(int(area_id), helm_chart, LoadRequest())
        self.state.performance_trace_replica = None

    @day2_function("/advance_trace_replica", [HttpRequestType.PUT])
    def advance_trace_replica(self) -> None:
        if self.state.performance_trace is None or self.state.performance_trace_replica is None:
            raise BlueprintNGException("The performance trace has not been started")

        next_replica = self.state.performance_trace_replica + 1
        if next_replica >= len(self.state.performance_trace.trace):
            raise BlueprintNGException("The performance trace is already at its last replica")

        self._apply_trace_replica(next_replica)
        self.state.performance_trace_replica = next_replica

    @day2_function("/previous_trace_replica", [HttpRequestType.PUT])
    def previous_trace_replica(self) -> None:
        """Apply the trace item immediately before the current one."""
        if self.state.performance_trace is None or self.state.performance_trace_replica is None:
            raise BlueprintNGException("The performance trace has not been started")

        previous_replica = self.state.performance_trace_replica - 1
        if previous_replica < 0:
            raise BlueprintNGException("The performance trace is already at its first replica")

        self._apply_trace_replica(previous_replica)
        self.state.performance_trace_replica = previous_replica

    @day2_function("/go_to_trace_sequence", [HttpRequestType.PUT])
    def go_to_trace_sequence(self, model: LoadGenPerformanceTraceSequence) -> None:
        """Apply the trace item with the requested sequence number."""
        performance_trace = self.state.performance_trace
        if performance_trace is None or not performance_trace.trace:
            raise BlueprintNGException("No performance trace has been loaded")

        replica_index = next(
            (
                index
                for index, trace_item in enumerate(performance_trace.trace)
                if trace_item.seq_number == model.seq_number
            ),
            None,
        )
        if replica_index is None:
            raise BlueprintNGException(
                f"Sequence number {model.seq_number} is not present in the performance trace"
            )

        self._apply_trace_replica(replica_index)
        self.state.performance_trace_replica = replica_index

    def _apply_trace_replica(self, replica_index: int) -> None:
        """Apply one performance trace replica to every target load generator."""
        performance_trace = self.state.performance_trace
        if performance_trace is None:
            raise BlueprintNGException("No performance trace has been loaded")

        vms = self.state.vms or {}
        k8s_helm_charts = self.state.k8s_helm_charts or {}
        replica = performance_trace.trace[replica_index]
        missing_areas = [
            area_id
            for area_id in replica.areas
            if str(area_id) not in vms and str(area_id) not in k8s_helm_charts
        ]
        if missing_areas:
            raise BlueprintNGException(f"No load generator deployed in areas {missing_areas}")

        for area_id, load_request in replica.areas.items():
            area_key = str(area_id)
            if area_key in vms:
                self._apply_load(int(area_id), vms[area_key], load_request)
            if area_key in k8s_helm_charts:
                self._apply_k8s_load(int(area_id), k8s_helm_charts[area_key], load_request)

    def _apply_k8s_load(
        self,
        area_id: int,
        helm_chart: HelmChartResource,
        load_request: LoadRequest,
    ) -> None:
        """Send a load request from an ephemeral container in a load generator pod."""
        deployments = helm_chart.deployments or {}
        pods = [pod for deployment in deployments.values() for pod in deployment.pods]
        if not pods:
            raise BlueprintNGException(f"Load generator Helm chart in area {area_id} has no running pod")

        self.provider.spawn_ephemeral_container_in_pod(
            helm_chart,
            pods[0].name,
            f"load-request-{uuid.uuid4().hex[:12]}",
            "curlimages/curl:8.16.0",
            ["curl"],
            [
                "--fail",
                "--silent",
                "--show-error",
                "--request",
                "POST",
                "--header",
                "Content-Type: application/json",
                "--data",
                json.dumps(load_request.model_dump(mode="json")),
                "http://127.0.0.1:3000/load",
            ],
        )

    @staticmethod
    def _apply_load(area_id: int, vm: VmResource, load_request: LoadRequest) -> None:
        """Send a load request to the load generator VM deployed in an area."""
        if not vm.access_ip:
            raise BlueprintNGException(f"Load generator VM in area {area_id} has no management IP")
        response = requests.post(
            f"http://{vm.access_ip}:3000/load",
            json=load_request.model_dump(mode="json"),
        )
        response.raise_for_status()
