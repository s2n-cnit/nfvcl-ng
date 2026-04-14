import copy
from typing import Optional, Dict, Tuple

from pydantic import Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_k8s import Generic5GK8sBlueprintNGState, Generic5GK8sBlueprintNG
from nfvcl.blueprints_ng.modules.open5gs import open5gs_default_core_config
from nfvcl.blueprints_ng.modules.open5gs.open5gs_upf.Open5GsUpf_blue import OPEN5GS_UPF_BLUE_TYPE
from nfvcl_common.utils.log import create_logger
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core_models.resources import HelmChartResource
from nfvcl_models.blueprint_ng.core5g.common import Create5gModel, SubArea, NetworkEndPointType
from nfvcl_models.blueprint_ng.g5.core import NF5GType, Core5GDelSubscriberModel, Core5GAddSubscriberModel
from nfvcl_models.blueprint_ng.g5.custom_types_5g import MCCType, MNCType
from nfvcl_models.blueprint_ng.open5gs.core import Open5gsCoreConfig, Open5gsSubscriber

OPEN5GS_CORE_BLUE_TYPE = "open5gs"
logger = create_logger('Open5Gs')


class Open5GsBlueprintNGState(Generic5GK8sBlueprintNGState):
    open5gs_config: Optional[Open5gsCoreConfig] = Field(default=None)
    mcc: Optional[MCCType] = Field(default=None)
    mnc: Optional[MNCType] = Field(default=None)


class Open5GsBlueCreateModel(Create5gModel):
    pass


@blueprint_type(OPEN5GS_CORE_BLUE_TYPE)
class Open5Gs(Generic5GK8sBlueprintNG[Open5GsBlueprintNGState, Open5GsBlueCreateModel]):
    default_upf_implementation = OPEN5GS_UPF_BLUE_TYPE

    def __init__(self, blueprint_id: str, state_type: type[Generic5GK8sBlueprintNGState] = Open5GsBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB.

        """
        super().__init__(blueprint_id, state_type)

    def network_functions_dictionary(self) -> Dict[NF5GType, Tuple[str, str]]:
        return {
            NF5GType.AMF: ("open5gs-amf", "open5gs-amf-ngap" if not self.state.open5gs_config.amf.multus.enabled else None),
            NF5GType.NRF: ("open5gs-nrf", "open5gs-nrf-sbi"),
            NF5GType.SMF: ("open5gs-smf", "open5gs-smf-pfcp" if not self.state.open5gs_config.smf.multus.enabled else None),
            NF5GType.DB: ("open5gs-mongodb", "open5gs-mongodb")
        }

    def create_5g(self, create_model: Create5gModel):
        self.logger.info("Starting creation of Open5Gs blueprint")

        core_area: SubArea = list(filter(lambda x: x.core, create_model.areas))[0]

        self.state.open5gs_config = copy.deepcopy(open5gs_default_core_config.default_core_config)

        # self.state.current_config = create_model
        self.state.core_helm_chart = HelmChartResource(
            area=core_area.id,
            name="open5gs",
            # repo="https://mysql.github.io/mysql-operator/",
            chart="helm_charts/charts/open5gs-2.7.6.tgz",
            chart_as_path=True,
            # version="9.19.1",
            namespace=self.id
        )
        self.register_resource(self.state.core_helm_chart)

        self.state.mcc = create_model.config.plmn[0:3]
        self.state.mnc = create_model.config.plmn[-2:]

        self.update_core_values()

        # In the chart installation a dict containing the values overrides can be passed
        self.provider.install_helm_chart(
            self.state.core_helm_chart,
            self.state.open5gs_config.model_dump(exclude_none=True, by_alias=True)
        )
        self.update_k8s_network_functions()

        for subscriber in create_model.config.subscribers.copy():
            self.add_ues(subscriber)

    def clear_core_values(self):
        # SMF
        self.state.open5gs_config.smf.config.upf.pfcp.clear()
        self.state.open5gs_config.smf.config.subnet_list.clear()
        self.state.open5gs_config.smf.config.info.clear()

        # AMF
        self.state.open5gs_config.amf.config.guami_list.clear()
        self.state.open5gs_config.amf.config.tai_list.clear()
        self.state.open5gs_config.amf.config.plmn_list.clear()

        # NRF
        self.state.open5gs_config.nrf.config.serving_list.clear()

        # NSSF
        self.state.open5gs_config.nssf.config.nsi_list.clear()

    def update_core_values(self):
        self.clear_core_values()

        if self.state.network_endpoints.n2 and self.state.network_endpoints.n2.type == NetworkEndPointType.MULTUS:
            self.state.open5gs_config.amf.multus.enabled = True
            self.state.open5gs_config.amf.config.ngap.dev = "n2"
            self.state.open5gs_config.amf.multus.n2network.set_multus(self.state.network_endpoints.n2.multus)
        else:
            self.state.open5gs_config.amf.services.ngap.type = "LoadBalancer"
        if self.state.network_endpoints.n4 and self.state.network_endpoints.n4.type == NetworkEndPointType.MULTUS:
            self.state.open5gs_config.smf.multus.enabled = True
            self.state.open5gs_config.smf.config.pfcp.dev = "n4"
            self.state.open5gs_config.smf.multus.n4network.set_multus(self.state.network_endpoints.n4.multus)
        else:
            self.state.open5gs_config.smf.services.pfcp.type = "LoadBalancer"

        self.state.open5gs_config.nrf.services.sbi.type = "LoadBalancer"

        # AMF
        self.state.open5gs_config.amf.config.add_guami_list_item(
            mcc=self.state.mcc,
            mnc=self.state.mnc
        )

        # NRF
        self.state.open5gs_config.nrf.add_serving_list_item(
            mcc=self.state.mcc,
            mnc=self.state.mnc
        )

        for sub_area in self.state.current_config.areas:
            upf_list = self.state.edge_areas[str(sub_area.id)].upf.upf_list
            if not upf_list:
                continue
            deployed_upf_info = upf_list[0]
            slices = self.state.current_config.get_slices_profiles_for_area(sub_area.id)

            # SMF
            self.state.open5gs_config.smf.add_info_item(
                _slices=slices,
                area_id=sub_area.id,
                mcc=self.state.mcc,
                mnc=self.state.mnc
            )

            # AMF
            self.state.open5gs_config.amf.config.add_plmn_list_item(
                mcc=self.state.mcc,
                mnc=self.state.mnc,
                snssai=slices
            )

            self.state.open5gs_config.amf.config.add_tai_list_item(
                mcc=self.state.mcc,
                mnc=self.state.mnc,
                area_id=sub_area.id
            )

            for _slice in sub_area.slices:
                sub_slice = self.state.current_config.get_slice_profile(_slice.sliceId)
                if sub_slice is None:
                    raise ValueError(f'Slice {_slice.sliceId} not found.')

                # NSSF
                self.state.open5gs_config.nssf.add_nsi_list_item(
                    snssai=sub_slice
                )
                for dnn in sub_slice.dnnList:
                    data_dnn = self.state.current_config.get_dnn(dnn)

                    # SMF
                    self.state.open5gs_config.smf.add_upf_addresses(deployed_upf_info.network_info.n4_ip.exploded, dnn)
                    self.state.open5gs_config.smf.add_subnet_item(data_dnn.pools[0].cidr, dnn)

    def update_core(self):
        self.update_core_values()
        self.provider.update_values_helm_chart(
            self.state.core_helm_chart,
            self.state.open5gs_config.model_dump(exclude_none=True, by_alias=True)
        )

    def wait_core_ready(self):
        pass

    def add_ues(self, subscriber: Core5GAddSubscriberModel):
        """Add a subscriber to the Open5GS MongoDB database."""
        subscriber_to_add = Open5gsSubscriber.from_create5g_model(subscriber, self.state.current_config)
        command = ["mongosh", "mongodb://open5gs-mongodb/open5gs", "--eval", subscriber_to_add.to_mongosh_insert()]

        response = self.provider.spawn_pod(
            helm_chart_resource=self.state.core_helm_chart,
            pod_name=f"mongosh-add-{subscriber.imsi}",
            image="mongo:7",
            command=command,
            wait_for_completion=True
        )
        self.logger.info(response)

    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        """Delete a subscriber from the Open5GS MongoDB database by IMSI."""
        command = [
            "mongosh",
            "mongodb://open5gs-mongodb/open5gs",
            "--eval",
            f'db.subscribers.deleteOne({{ imsi: "{subscriber_model.imsi}" }})'
        ]

        response = self.provider.spawn_pod(
            helm_chart_resource=self.state.core_helm_chart,
            pod_name=f"mongosh-del-{subscriber_model.imsi}",
            image="mongo:7",
            command=command,
            wait_for_completion=True
        )
        self.logger.info(response)
        self.logger.info(f"Deleted subscriber with IMSI: {subscriber_model.imsi}")
