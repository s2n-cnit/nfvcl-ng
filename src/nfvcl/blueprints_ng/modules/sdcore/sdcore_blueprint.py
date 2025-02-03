from __future__ import annotations

import copy
import time
from typing import Optional, Dict, Tuple

from pydantic import Field

from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_k8s import Generic5GK8sBlueprintNG, Generic5GK8sBlueprintNGState, \
    NF5GType
from nfvcl.blueprints_ng.modules.sdcore.sdcore_default_config import default_config
from nfvcl.blueprints_ng.modules.sdcore.sdcore_values_model import SDCoreValuesModel, SimAppYamlConfiguration
from nfvcl.blueprints_ng.modules.sdcore_upf.sdcore_upf_blueprint import SDCORE_UPF_BLUE_TYPE
from nfvcl_core.models.resources import HelmChartResource
from nfvcl.models.blueprint_ng.core5g.common import Create5gModel


class BlueSDCoreCreateModel(Create5gModel):
    pass


class SdCoreBlueprintNGState(Generic5GK8sBlueprintNGState):
    sdcore_config_values: Optional[SDCoreValuesModel] = Field(default=None)


@blueprint_type("sdcore")
class SdCoreBlueprintNG(Generic5GK8sBlueprintNG[SdCoreBlueprintNGState, BlueSDCoreCreateModel]):
    default_upf_implementation = SDCORE_UPF_BLUE_TYPE

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
            NF5GType.UDR: ("udr", "udr")
        }

    def create_5g(self, create_model: BlueSDCoreCreateModel):
        self.logger.info("Starting creation of SdCoreBlueprintNG blueprint")

        self.state.sdcore_config_values = copy.deepcopy(default_config)

        self.update_sdcore_values()

        self.state.core_helm_chart = HelmChartResource(
            area=list(filter(lambda x: x.core == True, self.state.current_config.areas))[0].id,
            name=f"sdcore",
            chart="helm_charts/charts/sdcore-1.0.0.tgz",
            chart_as_path=True,
            namespace=self.id
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

    def update_sdcore_values(self):
        """
        Update the SD-Core values from the current config present in the state
        This will also set the UPFs IPs on the slices
        """
        self.config_ref.from_generic_5g_model(self.state.current_config)

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
