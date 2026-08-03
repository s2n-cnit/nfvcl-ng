import copy
import json
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from pydantic import Field

from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_k8s import Generic5GK8sBlueprintNG, Generic5GK8sBlueprintNGState, \
    NF5GType
from nfvcl.blueprints_ng.modules.sdcore.sdcore_default_config import default_config
from nfvcl.blueprints_ng.modules.sdcore.sdcore_values_model import (
    DeviceGroup,
    NetworkSlice,
    SDCoreValuesModel,
    SimAppYamlConfiguration,
)
from nfvcl.blueprints_ng.modules.sdcore_upf.sdcore_upf_blueprint import SDCORE_UPF_BLUE_TYPE
from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_common.utils.blue_utils import rel_path
from nfvcl_common.utils.curl_utils import generate_curl_command, parse_curl_response
from nfvcl_core.blueprints.blueprint_ng import BlueprintNGException
from nfvcl_core_models.monitoring.monitoring import BlueprintMonitoringDefinition, GrafanaDashboard
from nfvcl_core_models.monitoring.prometheus_model import PrometheusTargetModel
from nfvcl_core_models.network.ipam_models import EndPointV4
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.core5g.common import Create5gModel, SubSliceProfiles
from nfvcl_models.blueprint_ng.g5.core import (
    Core5GAddTacModel,
    Core5GDelSliceModel,
    Core5GDelTacModel,
)


class BlueSDCoreCreateModel(Create5gModel):
    pass


class SdCoreBlueprintNGState(Generic5GK8sBlueprintNGState):
    sdcore_config_values: Optional[SDCoreValuesModel] = Field(default=None)


@blueprint_type("sdcore")
class SdCoreBlueprintNG(Generic5GK8sBlueprintNG[SdCoreBlueprintNGState, BlueSDCoreCreateModel]):
    default_upf_implementation = SDCORE_UPF_BLUE_TYPE
    NECESSARY_CORE_LB_IPS = 5
    START_UPFS_BEFORE_CORE = False

    WEBUI_CONFIG_BASE_URL = "http://webui:5000/config/v1"
    WEBUI_CONFIG_APPLY_TIMEOUT = 120
    WEBUI_CONFIG_POLL_INTERVAL = 5
    WEBUI_REQUEST_TIMEOUT = 10

    def __init__(self, blueprint_id: str, state_type: type[Generic5GK8sBlueprintNGState] = SdCoreBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    @property
    def config_ref(self) -> SimAppYamlConfiguration:
        return self.state.sdcore_config_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration

    def network_functions_dictionary(self) -> Dict[NF5GType, Tuple[str, str]]:
        return {
            NF5GType.AMF: ("amf", "amf"),
            NF5GType.AUSF: ("ausf", "ausf"),
            NF5GType.NRF: ("nrf", "nrf"),
            NF5GType.NSSF: ("nssf", "nssf"),
            NF5GType.PCF: ("pcf", "pcf"),
            NF5GType.SMF: ("smf", "smf"),
            NF5GType.UDM: ("udm", "udm"),
            NF5GType.UDR: ("udr", "udr"),
            NF5GType.METRICFUNC: ("metricfunc", "metricfunc")
        }

    def create_5g(self, create_model: BlueSDCoreCreateModel):
        self.logger.info("Starting creation of SdCoreBlueprintNG blueprint")

        self.state.sdcore_config_values = copy.deepcopy(default_config)

        self.update_sdcore_values()

        self.state.core_helm_chart = HelmChartResource(
            area=list(filter(lambda x: x.core, self.state.current_config.areas))[0].id,
            name="sdcore", # TODO should this include the blueprint id? Can we deploy multiple cores on the same blueprint?
            chart="helm_charts/charts/sdcore-1.0.0.tgz",
            chart_as_path=True,
            namespace=self.id,
            resource_group=self.id
        )
        self.register_resource(self.state.core_helm_chart)
        self.provider.install_helm_chart(self.state.core_helm_chart, self.state.sdcore_config_values.model_dump_for_helm())
        self.update_k8s_network_functions()

        # self.state.sdcore_config_values.omec_sub_provision.images.pull_policy = "Always"

        self.logger.debug(f"IP AMF: {self.get_amf_ip()}")

    def wait_core_ready(self):
        """
        Wait for the AMF to be ready, this is done to prevent the GNB connecting to the AMF before the configuration has been loaded by the core
        Without this wait the GNB need to be restarted manually after the core is done loading the config
        """
        while True:
            amf_logs = self.provider.get_pod_log(self.state.core_helm_chart, self.state.k8s_network_functions[NF5GType.AMF].deployment.pods[0].name, tail_lines=20)
            if "Sent Register NF Instance with updated profile" in amf_logs:
                break
            self.logger.debug("Waiting for AMF to be ready...")
            time.sleep(5)
        self.logger.debug("AMF ready")
        self.wait_webui_configuration_applied()

    @staticmethod
    def _expected_webui_device_group(device_group: DeviceGroup) -> dict[str, Any]:
        expected = device_group.model_dump(by_alias=True)
        expected["group-name"] = expected.pop("name")
        if expected["imsis"] == []:
            expected["imsis"] = None

        # The WebUI exposes MBR values in bits per second, while preserving the
        # unit from the configuration that was submitted by simapp.
        ue_dnn_qos = expected["ip-domain-expanded"]["ue-dnn-qos"]
        bitrate_multiplier = {
            "bps": 1,
            "kbps": 1_000,
            "mbps": 1_000_000,
            "gbps": 1_000_000_000,
        }[ue_dnn_qos["bitrate-unit"].lower()]
        ue_dnn_qos["dnn-mbr-downlink"] *= bitrate_multiplier
        ue_dnn_qos["dnn-mbr-uplink"] *= bitrate_multiplier
        return expected

    @staticmethod
    def _expected_webui_network_slice(network_slice: NetworkSlice) -> dict[str, Any]:
        expected = network_slice.model_dump(by_alias=True)
        expected["SliceName"] = expected.pop("name")
        expected["slice-id"]["sst"] = str(expected["slice-id"]["sst"])
        if expected["site-info"]["gNodeBs"] == []:
            expected["site-info"]["gNodeBs"] = None
        return expected

    def _get_webui_config(self, path: str) -> tuple[int, Any]:
        command = generate_curl_command(
            method=HttpRequestType.GET,
            url=f"{self.WEBUI_CONFIG_BASE_URL}/{path.lstrip('/')}",
            http2prio=False,
            as_list=True,
            include_response_body=True,
            connect_timeout=self.WEBUI_REQUEST_TIMEOUT,
            max_time=self.WEBUI_REQUEST_TIMEOUT,
        )
        response = self.provider.spawn_pod(
            helm_chart_resource=self.state.core_helm_chart,
            pod_name=f"sdcore-webui-{uuid.uuid4().hex[:8]}",
            image="curlimages/curl:latest",
            command=command,
            wait_for_completion=True,
            timeout=self.WEBUI_REQUEST_TIMEOUT + 10,
        )
        body, status_code = parse_curl_response(response)
        try:
            return status_code, json.loads(body)
        except json.JSONDecodeError as error:
            raise BlueprintNGException(
                f"SD-Core WebUI returned invalid JSON for '{path}': {body!r}"
            ) from error

    @staticmethod
    def _webui_network_slice_matches(actual: Any, expected: dict[str, Any]) -> bool:
        if actual == expected:
            return True
        if not isinstance(actual, dict):
            return False

        actual_site_info = actual.get("site-info")
        expected_site_info = expected.get("site-info")
        if not isinstance(actual_site_info, dict) or not isinstance(expected_site_info, dict):
            return False

        actual_upf = actual_site_info.get("upf")
        expected_upf = expected_site_info.get("upf")
        if not isinstance(actual_upf, dict) or not isinstance(expected_upf, dict):
            return False

        if expected_site_info.get("gNodeBs") is not None or expected_upf.get("upf-name") != "PLACEHOLDER":
            return False

        # Work around a simapp/WebUI reconciliation bug: simapp does not
        # detect removed gNBs, nor an UPF-name-only change when its port stays
        # unchanged. An unassigned slice can therefore retain both stale
        # values in WebUI even though the desired Helm configuration is empty.
        comparable_actual = copy.deepcopy(actual)
        comparable_actual["site-info"]["gNodeBs"] = None
        comparable_actual["site-info"]["upf"]["upf-name"] = "PLACEHOLDER"
        return comparable_actual == expected

    def _webui_configuration_mismatch(self) -> Optional[str]:
        expected_device_groups = {
            device_group.name: self._expected_webui_device_group(device_group)
            for device_group in self.config_ref.device_groups
        }
        status_code, actual_device_group_names = self._get_webui_config("device-group")
        if status_code != 200:
            return f"device-group list returned HTTP {status_code}"
        if not isinstance(actual_device_group_names, list):
            return f"device-group list returned {actual_device_group_names!r}"
        if set(actual_device_group_names) != set(expected_device_groups):
            return (
                f"device-group names are {sorted(actual_device_group_names)!r}, "
                f"expected {sorted(expected_device_groups)!r}"
            )

        for group_name, expected_device_group in expected_device_groups.items():
            status_code, actual_device_group = self._get_webui_config(f"device-group/{group_name}")
            if status_code != 200:
                return f"device-group '{group_name}' returned HTTP {status_code}"
            if actual_device_group != expected_device_group:
                return (
                    f"device-group '{group_name}' is {actual_device_group!r}, "
                    f"expected {expected_device_group!r}"
                )

        expected_network_slices = {
            network_slice.name: self._expected_webui_network_slice(network_slice)
            for network_slice in self.config_ref.network_slices
        }
        status_code, actual_network_slice_names = self._get_webui_config("network-slice")
        if status_code != 200:
            return f"network-slice list returned HTTP {status_code}"
        if not isinstance(actual_network_slice_names, list):
            return f"network-slice list returned {actual_network_slice_names!r}"
        if set(actual_network_slice_names) != set(expected_network_slices):
            return (
                f"network-slice names are {sorted(actual_network_slice_names)!r}, "
                f"expected {sorted(expected_network_slices)!r}"
            )

        for slice_name, expected_network_slice in expected_network_slices.items():
            status_code, actual_network_slice = self._get_webui_config(f"network-slice/{slice_name}")
            if status_code != 200:
                return f"network-slice '{slice_name}' returned HTTP {status_code}"
            if not self._webui_network_slice_matches(actual_network_slice, expected_network_slice):
                return (
                    f"network-slice '{slice_name}' is {actual_network_slice!r}, "
                    f"expected {expected_network_slice!r}"
                )

        return None

    def wait_webui_configuration_applied(self):
        deadline = time.monotonic() + self.WEBUI_CONFIG_APPLY_TIMEOUT
        last_mismatch = "WebUI configuration has not been checked"

        while time.monotonic() < deadline:
            try:
                mismatch = self._webui_configuration_mismatch()
                if mismatch is None:
                    self.logger.info("SD-Core configuration is available through WebUI")
                    return
                last_mismatch = mismatch
            except Exception as error:
                last_mismatch = str(error)

            self.logger.debug(f"Waiting for SD-Core WebUI configuration: {last_mismatch}")
            time.sleep(self.WEBUI_CONFIG_POLL_INTERVAL)

        raise BlueprintNGException(
            f"SD-Core configuration was not applied within {self.WEBUI_CONFIG_APPLY_TIMEOUT}s: "
            f"{last_mismatch}"
        )

    def update_sdcore_values(self):
        """
        Update the SD-Core values from the current config present in the state
        This will also set the UPFs IPs on the slices
        """
        self.config_ref.from_generic_5g_model(self.state.current_config)
        if self.state.network_endpoints.n2:
            self.state.sdcore_config_values.field_5g_control_plane.global_.n2network.set_multus(True, self.state.network_endpoints.n2.multus)
            self.state.sdcore_config_values.field_5g_control_plane.config.amf.ngapp.enabled = False
            self.state.sdcore_config_values.field_5g_control_plane.config.amf.ngapp.n2if = self.state.network_endpoints.n2.multus.ip_address.exploded
        if self.state.network_endpoints.n4:
            self.state.sdcore_config_values.field_5g_control_plane.global_.n4network.set_multus(True, self.state.network_endpoints.n4.multus)
            self.state.sdcore_config_values.field_5g_control_plane.config.smf.n4.isPfcpNeeded = True
            self.state.sdcore_config_values.field_5g_control_plane.config.smf.n4.n4if = self.state.network_endpoints.n4.multus.ip_address.exploded
            self.state.sdcore_config_values.field_5g_control_plane.config.smf.cfg_files.smfcfg_conf.configuration.pfcp.addr = self.state.network_endpoints.n4.multus.ip_address.exploded

        # TODO fix this
        if self.state.current_config.config.persistence.enabled:
            self.logger.warning("Persistence is enabled but it is not supported by the current blueprint version")
        #self.state.sdcore_config_values.field_5g_control_plane.mongodb.persistence.enabled = self.state.current_config.config.persistence.enabled
        # TODO this value does not exist in the current config
        # self.state.sdcore_config_values.field_5g_control_plane.mongodb.persistence.storage_class = self.state.current_config.config.persistence.storage_class

        for area in self.state.current_config.areas:
            for slice in area.slices:
                edge_info = self.get_upfs_for_slice(slice.sliceId)[0]
                # TODO deve dare errore se ne trova più di uno
                self.logger.debug(f"Setting UPF for slice {slice}: {edge_info.network_info.n4_ip.exploded}")
                self.config_ref.set_upf_ip(slice.sliceId, edge_info.network_info.n4_ip.exploded)

    def update_core(self):
        """
        Update the configuration of the deployed core
        """
        self.update_sdcore_values()
        self.provider.update_values_helm_chart(self.state.core_helm_chart, self.state.sdcore_config_values.model_dump_for_helm())
        self.wait_webui_configuration_applied()

    def add_slice(self, add_slice_model: SubSliceProfiles, oss: bool):
        self.update_edge_areas(start_upfs=False)
        self.update_core()
        self.update_edge_areas(start_upfs=True)
        self.update_gnb_configs()

    def add_tac(self, add_area_model: Core5GAddTacModel):
        self.update_edge_areas(start_upfs=False)
        self.update_core()
        self.update_edge_areas(start_upfs=True)
        self.update_gnb_configs()

    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_configs()

    def del_tac(self, del_area_model: Core5GDelTacModel):
        self.update_core()
        self.update_edge_areas()
        self.update_gnb_configs()

    def blueprint_monitoring_definition(self) -> Optional[BlueprintMonitoringDefinition]:
        monitoring_ip = self.state.k8s_network_functions[NF5GType.METRICFUNC].service.external_ip[0]

        return BlueprintMonitoringDefinition(
            prometheus_targets=[
                PrometheusTargetModel(endpoints=[EndPointV4(ip=monitoring_ip,port=9089)])
            ],
            grafana_dashboards=[
                GrafanaDashboard(name="sdcore", path=str(rel_path("dashboards/sdcore.json"))),
            ]
        )
