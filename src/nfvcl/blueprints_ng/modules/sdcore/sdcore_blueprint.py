from __future__ import annotations

import copy
from typing import Optional, Dict, Tuple

from pydantic import Field

from nfvcl.blueprints_ng.blueprint_ng import BlueprintNG
from nfvcl.blueprints_ng.lcm.blueprint_manager import get_blueprint_manager
from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_k8s import Generic5GK8sBlueprintNG, Generic5GK8sBlueprintNGState, \
    NF5GType
from nfvcl.blueprints_ng.modules.sdcore.sdcore_default_config import default_config
from nfvcl.blueprints_ng.modules.sdcore.sdcore_values_model import SDCoreValuesModel, SimAppYamlConfiguration
from nfvcl.blueprints_ng.modules.sdcore_upf.sdcore_upf_blueprint import SdCoreUPFCreateModel
from nfvcl.blueprints_ng.resources import HelmChartResource
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint_ng.core5g.common import Create5gModel
from nfvcl.models.blueprint_ng.g5.core import Core5GAddSubscriberModel, Core5GDelSubscriberModel, Core5GAddSliceModel, \
    Core5GDelSliceModel, Core5GAddTacModel, Core5GDelTacModel
from nfvcl.models.blueprint_ng.g5.upf import BlueCreateModelNetworks


class BlueSDCoreCreateModel(Create5gModel):
    pass


class SDCoreEdgeInfo(NFVCLBaseModel):
    blue_id: str = Field()
    n4_ip: str = Field()


class SdCoreBlueprintNGState(Generic5GK8sBlueprintNGState):
    sdcore_config_values: Optional[SDCoreValuesModel] = Field(default=None)
    edge_areas: Dict[str, Dict[str, SDCoreEdgeInfo]] = Field(default_factory=dict)


@blueprint_type("sdcore")
class SdCoreBlueprintNG(Generic5GK8sBlueprintNG, BlueprintNG[SdCoreBlueprintNGState, BlueSDCoreCreateModel]):
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
        self.logger.info("Starting creation of example blueprint")

        self.state.sdcore_config_values = copy.deepcopy(default_config)

        self.update_upf_deployments()
        self.update_sdcore_values()

        self.state.core_helm_chart = HelmChartResource(
            area=list(filter(lambda x: x.core == True, self.state.current_config.areas))[0].id,
            name=f"sdcore",
            chart="helm_charts/charts/sdcore-0.13.2.tgz",
            chart_as_path=True,
            namespace=self.id
        )
        self.register_resource(self.state.core_helm_chart)
        self.provider.install_helm_chart(self.state.core_helm_chart, self.state.sdcore_config_values.model_dump_for_helm())
        self.update_k8s_network_functions()

        self.update_gnb_config()

        # self.state.sdcore_config_values.omec_sub_provision.images.pull_policy = "Always"

        self.logger.debug(f"IP AMF: {self.state.k8s_network_functions[NF5GType.AMF].service.external_ip[0]}")

    def deploy_upf(self, area_id: int, dnn: str):
        """
        Deploy a UPF in the given area for the given dnn
        Args:
            area_id: Area in which the UPF will be deployed
            dnn: DNN that the UPF will serve
        """
        upf_networks = BlueCreateModelNetworks(
            mgt=self.state.current_config.config.network_endpoints.mgt,
            n4=self.state.current_config.config.network_endpoints.wan,
            n3=self.state.current_config.config.network_endpoints.n3,
            n6=self.state.current_config.config.network_endpoints.n6
        )

        dnn_ip_pool = list(filter(lambda x: x.dnn == dnn, self.state.current_config.config.network_endpoints.data_nets))[0].pools[0].cidr

        sdcore_upf_create_model = SdCoreUPFCreateModel(
            area_id=area_id,
            networks=upf_networks,
            dnn=dnn,
            gnb_n3_ip="PLACEHOLDER",
            gnb_n3_mac="PLACEHOLDER",
            start=False,
            ue_ip_pool_cidr=dnn_ip_pool
        )

        sdcore_upf_id = get_blueprint_manager().create_blueprint(sdcore_upf_create_model, "sdcore_upf", wait=True, parent_id=self.id)
        self.register_children(sdcore_upf_id)
        upf_n4_ip = self.call_external_function(sdcore_upf_id, "get_n4_info")
        sdcore_edge_info = SDCoreEdgeInfo(blue_id=sdcore_upf_id, n4_ip=upf_n4_ip)

        area_dict = self.state.edge_areas[str(area_id)]
        if not area_dict:
            area_dict = {}
        area_dict[dnn] = sdcore_edge_info
        self.state.edge_areas[str(area_id)] = area_dict

    def undeploy_upf(self, area_id: int, dnn: str):
        """
        Remove a deployed UPF
        Args:
            area_id: Area of the UPF to undeploy
            dnn: DNN of the UPF to undeploy
        """
        blue_id = self.state.edge_areas[str(area_id)][dnn].blue_id
        get_blueprint_manager().delete_blueprint(blue_id, wait=True)
        self.deregister_children(blue_id)
        del self.state.edge_areas[str(area_id)][dnn]

    def update_sdcore_values(self):
        """
        Update the SD-Core values from the current config present in the state
        This will also set the UPFs IPs on the slices
        """
        self.config_ref.from_generic_5g_model(self.state.current_config)

        for area in self.state.current_config.areas:
            for slice in area.slices:
                dnn = list(filter(lambda x: x.sliceId == slice.sliceId, self.state.current_config.config.sliceProfiles))[0].dnnList[0]
                sdcore_edge_info = self.state.edge_areas[str(area.id)][dnn]
                self.logger.debug(f"Setting UPF for slice {slice}: {sdcore_edge_info.n4_ip}")
                self.config_ref.set_upf_ip(slice.sliceId, sdcore_edge_info.n4_ip)

    def update_core(self):
        """
        Update the configuration of the deployed core
        """
        self.provider.update_values_helm_chart(self.state.core_helm_chart, self.state.sdcore_config_values.model_dump_for_helm())

    def update_upf_deployments(self):
        """
        Update the UPF deployments to match the current configuration
        this will undeploy the ones that are not needed anymore and add new ones
        """
        for area in self.state.current_config.areas:
            if str(area.id) not in self.state.edge_areas:
                self.state.edge_areas[str(area.id)] = {}

            dnns_to_deploy_in_area = []
            for slice in area.slices:
                dnn = list(filter(lambda x: x.sliceId == slice.sliceId, self.state.current_config.config.sliceProfiles))[0].dnnList[0]
                dnns_to_deploy_in_area.append(dnn)

            dnns_to_deploy_in_area = list(set(dnns_to_deploy_in_area))

            for dnn in list(self.state.edge_areas[str(area.id)].keys()):
                if dnn not in dnns_to_deploy_in_area:
                    self.logger.info(f"Undeploying UPF for dnn '{dnn}' in area '{area.id}'")
                    self.undeploy_upf(area.id, dnn)

            for dnn in dnns_to_deploy_in_area:
                if dnn not in list(self.state.edge_areas[str(area.id)].keys()):
                    self.logger.info(f"Deploying UPF for dnn '{dnn}' in area '{area.id}'")
                    self.deploy_upf(area.id, dnn)

    def add_ues(self, subscriber_model: Core5GAddSubscriberModel):
        self.update_sdcore_values()
        self.update_core()

    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        self.update_sdcore_values()
        self.update_core()

    def add_slice(self, add_slice_model: Core5GAddSliceModel, oss: bool):
        self.update_upf_deployments()
        self.update_gnb_config()
        self.update_sdcore_values()
        self.update_core()

    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        # TODO what about subscribers on this slice?
        self.update_upf_deployments()
        self.update_gnb_config()
        self.update_sdcore_values()
        self.update_core()

    def add_tac(self, add_area_model: Core5GAddTacModel):
        self.update_upf_deployments()
        self.update_gnb_config()
        self.update_sdcore_values()
        self.update_core()

    def del_tac(self, del_area_model: Core5GDelTacModel):
        self.update_upf_deployments()
        self.update_gnb_config()
        self.update_sdcore_values()
        self.update_core()
